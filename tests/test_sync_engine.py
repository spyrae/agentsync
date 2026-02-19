"""Tests for agentsync.sync — SyncEngine with fake adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentsync.adapters.base import (
    Section,
    ServerConfig,
    SourceAdapter,
    TargetAdapter,
    ValidationResult,
    WriteResult,
)
from agentsync.config import AgentSyncConfig, RulesConfig, SyncOptions, TargetConfig
from agentsync.sync import SyncEngine

# ===================================================================
# Fake adapters
# ===================================================================


class FakeSource(SourceAdapter):
    def __init__(
        self,
        servers: dict[str, ServerConfig] | None = None,
        sections: list[Section] | None = None,
    ) -> None:
        self._servers = servers or {}
        self._sections = sections or []

    def load_servers(self) -> dict[str, ServerConfig]:
        return dict(self._servers)

    def load_rules(self) -> list[Section]:
        return list(self._sections)


@dataclass
class FakeTarget(TargetAdapter):
    name: str = "fake"
    generated_mcp: dict[str, ServerConfig] = field(default_factory=dict)
    generated_rules: list[Section] = field(default_factory=list)
    write_results: list[WriteResult] = field(default_factory=list)
    raise_on_write: bool = False

    def generate_mcp(self, servers: dict[str, ServerConfig]) -> dict[str, Any]:
        self.generated_mcp = servers
        return {"mcpServers": {k: v.config for k, v in servers.items()}}

    def generate_rules(self, sections: list[Section]) -> str:
        self.generated_rules = sections
        return "\n".join(s.content for s in sections)

    def write(self, dry_run: bool = False) -> list[WriteResult]:
        if self.raise_on_write:
            raise RuntimeError("write failed")
        return list(self.write_results)

    def validate(self) -> list[ValidationResult]:
        return []


# ===================================================================
# Helpers
# ===================================================================


def _config(
    target_names: list[str] | None = None,
    exclude_sections: list[str] | None = None,
    target_overrides: dict[str, dict[str, Any]] | None = None,
) -> AgentSyncConfig:
    names = target_names or ["t1"]
    overrides = target_overrides or {}
    targets = {}
    for n in names:
        kw = overrides.get(n, {})
        targets[n] = TargetConfig(type="fake", **kw)
    return AgentSyncConfig(
        targets=targets,
        rules=RulesConfig(exclude_sections=exclude_sections or []),
        sync=SyncOptions(),
    )


def _servers(*names: str) -> dict[str, ServerConfig]:
    return {n: ServerConfig(name=n, config={"command": "test"}) for n in names}


def _sections(*headers: str) -> list[Section]:
    return [Section(header=h, level=2, content=f"## {h}\nBody") for h in headers]


# ===================================================================
# Tests
# ===================================================================


def test_basic_sync():
    source = FakeSource(servers=_servers("a", "b"))
    t1 = FakeTarget()
    cfg = _config()
    engine = SyncEngine(cfg, source, {"t1": t1})

    result = engine.run()

    assert result.success is True
    assert "t1" in result.target_results
    assert set(t1.generated_mcp) == {"a", "b"}


def test_mcp_only_skips_rules():
    source = FakeSource(
        servers=_servers("s1"),
        sections=_sections("Section"),
    )
    t1 = FakeTarget()
    engine = SyncEngine(_config(), source, {"t1": t1})

    engine.run(mcp_only=True)

    assert t1.generated_mcp  # MCP processed
    assert t1.generated_rules == []  # Rules skipped


def test_rules_only_skips_mcp():
    source = FakeSource(
        servers=_servers("s1"),
        sections=_sections("Section"),
    )
    t1 = FakeTarget()
    engine = SyncEngine(_config(), source, {"t1": t1})

    engine.run(rules_only=True)

    assert t1.generated_mcp == {}  # MCP skipped
    assert len(t1.generated_rules) == 1  # Rules processed


def test_target_filter():
    source = FakeSource(servers=_servers("s1"))
    t1 = FakeTarget(name="t1")
    t2 = FakeTarget(name="t2")
    cfg = _config(target_names=["t1", "t2"])
    engine = SyncEngine(cfg, source, {"t1": t1, "t2": t2})

    result = engine.run(target_filter="t1")

    assert "t1" in result.target_results
    assert "t2" not in result.target_results


def test_unknown_target_filter():
    source = FakeSource()
    engine = SyncEngine(_config(), source, {"t1": FakeTarget()})

    result = engine.run(target_filter="nonexistent")

    assert result.success is False


def test_exclude_servers():
    source = FakeSource(servers=_servers("keep", "drop"))
    t1 = FakeTarget()
    cfg = _config(target_overrides={"t1": {"exclude_servers": ["drop"]}})
    engine = SyncEngine(cfg, source, {"t1": t1})

    engine.run()

    assert "keep" in t1.generated_mcp
    assert "drop" not in t1.generated_mcp


def test_protocol_filter_stdio():
    srv = {
        "stdio_srv": ServerConfig(name="stdio_srv", config={"command": "x"}),
        "http_srv": ServerConfig(name="http_srv", config={"url": "http://x"}),
    }
    source = FakeSource(servers=srv)
    t1 = FakeTarget()
    cfg = _config(target_overrides={"t1": {"protocols": ["stdio"]}})
    engine = SyncEngine(cfg, source, {"t1": t1})

    engine.run()

    assert "stdio_srv" in t1.generated_mcp
    assert "http_srv" not in t1.generated_mcp


def test_protocol_filter_multi_passes_both():
    """With protocols=['stdio','http'], servers of EITHER type should pass."""
    srv = {
        "stdio_srv": ServerConfig(name="stdio_srv", config={"command": "x"}),
        "http_srv": ServerConfig(name="http_srv", config={"url": "http://x"}),
    }
    source = FakeSource(servers=srv)
    t1 = FakeTarget()
    cfg = _config(target_overrides={"t1": {"protocols": ["stdio", "http"]}})
    engine = SyncEngine(cfg, source, {"t1": t1})

    engine.run()

    assert "stdio_srv" in t1.generated_mcp
    assert "http_srv" in t1.generated_mcp


def test_target_write_error_captured():
    source = FakeSource(servers=_servers("s1"))
    t1 = FakeTarget(raise_on_write=True)
    engine = SyncEngine(_config(), source, {"t1": t1})

    result = engine.run()

    assert result.success is False
    tr = result.target_results["t1"]
    assert not tr.success
    assert tr.errors
