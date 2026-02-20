"""Tests for agentsync.adapters.antigravity — AntigravityTargetAdapter."""

from __future__ import annotations

import json
from pathlib import Path

from agentsync.adapters.antigravity import AntigravityTargetAdapter
from agentsync.adapters.base import Section, ServerConfig
from agentsync.config import (
    AgentSyncConfig,
    RulesConfig,
    SourceConfig,
    SyncOptions,
    TargetConfig,
)

# ===================================================================
# Helpers
# ===================================================================


def _sc(name: str, **extra: object) -> ServerConfig:
    cfg: dict = {"command": "node", "args": ["server.js"]}
    cfg.update(extra)
    return ServerConfig(name=name, config=cfg)


def _servers(*names: str) -> dict[str, ServerConfig]:
    return {n: _sc(n) for n in names}


def _sections(*headers: str) -> list[Section]:
    return [Section(header=h, level=2, content=f"## {h}\n\nContent for {h}.") for h in headers]


def _config(
    tmp_path: Path,
    *,
    mcp_path: str = "mcp.json",
    exclude_servers: list[str] | None = None,
) -> tuple[TargetConfig, AgentSyncConfig]:
    tc = TargetConfig(
        type="antigravity",
        mcp_path=mcp_path,
        protocols=["stdio"],
        exclude_servers=exclude_servers or [],
    )
    cfg = AgentSyncConfig(
        source=SourceConfig(
            global_config=str(tmp_path / ".claude.json"),
            project_mcp=str(tmp_path / ".mcp.json"),
            rules_file=str(tmp_path / "CLAUDE.md"),
        ),
        targets={"antigravity": tc},
        rules=RulesConfig(),
        sync=SyncOptions(backup=False),
        config_dir=tmp_path,
    )
    return tc, cfg


# ===================================================================
# generate_mcp
# ===================================================================


class TestGenerateMcp:
    def test_basic(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        result = adapter.generate_mcp(_servers("a", "b"))
        assert "mcpServers" in result
        assert set(result["mcpServers"]) == {"a", "b"}

    def test_empty_servers(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        result = adapter.generate_mcp({})
        assert result == {"mcpServers": {}}


# ===================================================================
# generate_rules (noop)
# ===================================================================


class TestGenerateRules:
    def test_returns_empty(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        assert adapter.generate_rules(_sections("Style")) == ""

    def test_returns_empty_no_sections(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        assert adapter.generate_rules([]) == ""


# ===================================================================
# write
# ===================================================================


class TestWrite:
    def test_creates_file(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        adapter.generate_mcp(_servers("srv"))
        results = adapter.write()
        assert any(r.written for r in results)
        data = json.loads((tmp_path / "mcp.json").read_text())
        assert "srv" in data["mcpServers"]

    def test_dry_run(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        adapter.generate_mcp(_servers("srv"))
        results = adapter.write(dry_run=True)
        assert all(not r.written for r in results)
        assert not (tmp_path / "mcp.json").exists()

    def test_skips_rules(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        adapter.generate_rules(_sections("Style"))
        adapter.generate_mcp(_servers("a"))
        results = adapter.write()
        # Only MCP should be written, no rules file
        written_paths = [r.path for r in results if r.written]
        assert len(written_paths) == 1
        assert "mcp.json" in written_paths[0]


# ===================================================================
# validate
# ===================================================================


class TestValidate:
    def test_consistent(self, tmp_path: Path):
        (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"a": {"command": "x"}}}))
        (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {"a": {}}}))
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        results = adapter.validate()
        server_check = [r for r in results if "consistency" in r.name]
        assert all(r.passed for r in server_check)

    def test_missing_server(self, tmp_path: Path):
        (tmp_path / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"a": {"command": "x"}, "b": {"command": "y"}}})
        )
        (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {"a": {}}}))
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        results = adapter.validate()
        server_check = [r for r in results if "consistency" in r.name]
        assert any(not r.passed for r in server_check)

    def test_no_file(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = AntigravityTargetAdapter(tc, cfg)
        results = adapter.validate()
        assert all(r.passed for r in results)
        assert all(r.severity == "info" for r in results)
