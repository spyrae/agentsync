"""Tests for agentsync.adapters.codex — CodexTargetAdapter."""

from __future__ import annotations

import json
from pathlib import Path

from agentsync.adapters.base import Section, ServerConfig
from agentsync.adapters.codex import (
    MARKER_END,
    MARKER_START,
    CodexTargetAdapter,
    _extract_server_names,
    _server_to_toml,
    _toml_value,
)
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
    config_path: str = "config.toml",
    rules_path: str = "AGENTS.md",
    exclude_servers: list[str] | None = None,
) -> tuple[TargetConfig, AgentSyncConfig]:
    tc = TargetConfig(
        type="codex",
        config_path=config_path,
        rules_path=rules_path,
        exclude_servers=exclude_servers or [],
    )
    cfg = AgentSyncConfig(
        source=SourceConfig(
            global_config=str(tmp_path / ".claude.json"),
            project_mcp=str(tmp_path / ".mcp.json"),
            rules_file=str(tmp_path / "CLAUDE.md"),
        ),
        targets={"codex": tc},
        rules=RulesConfig(),
        sync=SyncOptions(backup=False),
        config_dir=tmp_path,
    )
    return tc, cfg


# ===================================================================
# _toml_value
# ===================================================================


class TestTomlValue:
    def test_string(self):
        assert _toml_value("hello") == '"hello"'
        assert _toml_value('say "hi"') == '"say \\"hi\\""'

    def test_bool(self):
        assert _toml_value(True) == "true"
        assert _toml_value(False) == "false"

    def test_int_and_float(self):
        assert _toml_value(42) == "42"
        assert _toml_value(3.14) == "3.14"

    def test_list(self):
        assert _toml_value([1, "a", True]) == '[1, "a", true]'

    def test_dict(self):
        result = _toml_value({"key": "val"})
        assert result == '{key = "val"}'


# ===================================================================
# _server_to_toml
# ===================================================================


class TestServerToToml:
    def test_basic(self):
        toml = _server_to_toml("my-server", {"command": "npx", "args": ["-y", "pkg"]})
        assert "[mcp_servers.my_server]" in toml
        assert 'command = "npx"' in toml
        assert 'args = ["-y", "pkg"]' in toml

    def test_http_server(self):
        toml = _server_to_toml("api", {"url": "https://example.com"})
        assert "[mcp_servers.api]" in toml
        assert 'url = "https://example.com"' in toml


# ===================================================================
# generate_mcp
# ===================================================================


class TestGenerateMcp:
    def test_basic(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        text = adapter.generate_mcp(_servers("ctx7"))
        assert MARKER_START in text
        assert MARKER_END in text
        assert "[mcp_servers.ctx7]" in text

    def test_empty_servers(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        text = adapter.generate_mcp({})
        assert MARKER_START in text
        assert MARKER_END in text


# ===================================================================
# generate_rules
# ===================================================================


class TestGenerateRules:
    def test_basic(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        text = adapter.generate_rules(_sections("Code Style"))
        assert "## Code Style" in text

    def test_empty(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        text = adapter.generate_rules([])
        assert text == ""


# ===================================================================
# write
# ===================================================================


class TestWrite:
    def test_new_file(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        adapter.generate_mcp(_servers("a"))
        results = adapter.write()
        assert any(r.written for r in results)
        content = (tmp_path / "config.toml").read_text()
        assert MARKER_START in content
        assert "[mcp_servers.a]" in content

    def test_preserves_existing(self, tmp_path: Path):
        # Write a pre-existing config.toml with markers
        existing = (
            "[model]\nprovider = \"openai\"\n\n"
            f"{MARKER_START}\n"
            "[mcp_servers.old]\ncommand = \"old\"\n\n"
            f"{MARKER_END}\n\n"
            "[extra]\nfoo = true\n"
        )
        (tmp_path / "config.toml").write_text(existing)

        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        adapter.generate_mcp(_servers("new_srv"))
        adapter.write()

        content = (tmp_path / "config.toml").read_text()
        assert "[model]" in content
        assert "[extra]" in content
        assert "[mcp_servers.new_srv]" in content
        assert "[mcp_servers.old]" not in content

    def test_appends_markers(self, tmp_path: Path):
        # File without markers
        (tmp_path / "config.toml").write_text("[model]\nprovider = \"openai\"\n")

        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        adapter.generate_mcp(_servers("srv"))
        adapter.write()

        content = (tmp_path / "config.toml").read_text()
        assert "[model]" in content
        assert MARKER_START in content
        assert "[mcp_servers.srv]" in content

    def test_dry_run(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        adapter.generate_mcp(_servers("a"))
        results = adapter.write(dry_run=True)
        assert all(not r.written for r in results)
        assert not (tmp_path / "config.toml").exists()

    def test_write_rules(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        adapter.generate_rules(_sections("Style"))
        results = adapter.write()
        assert any(r.written for r in results)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "## Style" in content


# ===================================================================
# validate
# ===================================================================


class TestValidate:
    def test_with_markers(self, tmp_path: Path):
        (tmp_path / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"a": {"command": "x"}}})
        )
        toml = (
            f"{MARKER_START}\n"
            "[mcp_servers.a]\ncommand = \"x\"\n\n"
            f"{MARKER_END}\n"
        )
        (tmp_path / "config.toml").write_text(toml)

        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        results = adapter.validate()
        server_check = [r for r in results if "consistency" in r.name]
        assert all(r.passed for r in server_check)

    def test_no_markers(self, tmp_path: Path):
        (tmp_path / "config.toml").write_text("[model]\nprovider = \"openai\"\n")

        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        results = adapter.validate()
        assert any(r.severity == "warning" for r in results)

    def test_no_file(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CodexTargetAdapter(tc, cfg)
        results = adapter.validate()
        assert all(r.passed for r in results)
        assert all(r.severity == "info" for r in results)


# ===================================================================
# _extract_server_names
# ===================================================================


class TestExtractServerNames:
    def test_basic(self):
        content = "[mcp_servers.foo]\n[mcp_servers.bar]\n"
        assert _extract_server_names(content) == {"foo", "bar"}

    def test_empty(self):
        assert _extract_server_names("nothing here") == set()
