"""Tests for agentsync.adapters.cursor — CursorTargetAdapter."""

from __future__ import annotations

import json
from pathlib import Path

from agentsync.adapters.base import Section, ServerConfig
from agentsync.adapters.cursor import CursorTargetAdapter
from agentsync.config import (
    AgentSyncConfig,
    RulesConfig,
    SourceConfig,
    SyncOptions,
    TargetConfig,
)
from agentsync.sync import SyncEngine

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
    rules_path: str = "rules.mdc",
    rules_format: str = "mdc",
    exclude_servers: list[str] | None = None,
    exclude_sections: list[str] | None = None,
) -> tuple[TargetConfig, AgentSyncConfig]:
    tc = TargetConfig(
        type="cursor",
        mcp_path=mcp_path,
        rules_path=rules_path,
        rules_format=rules_format,
        exclude_servers=exclude_servers or [],
    )
    cfg = AgentSyncConfig(
        source=SourceConfig(
            global_config=str(tmp_path / ".claude.json"),
            project_mcp=str(tmp_path / ".mcp.json"),
            rules_file=str(tmp_path / "CLAUDE.md"),
        ),
        targets={"cursor": tc},
        rules=RulesConfig(exclude_sections=exclude_sections or []),
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
        adapter = CursorTargetAdapter(tc, cfg)
        result = adapter.generate_mcp(_servers("ctx7", "supabase"))
        assert "mcpServers" in result
        assert set(result["mcpServers"]) == {"ctx7", "supabase"}

    def test_empty_servers(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CursorTargetAdapter(tc, cfg)
        result = adapter.generate_mcp({})
        assert result == {"mcpServers": {}}


# ===================================================================
# generate_rules
# ===================================================================


class TestGenerateRules:
    def test_mdc_format(self, tmp_path: Path):
        tc, cfg = _config(tmp_path, rules_format="mdc")
        adapter = CursorTargetAdapter(tc, cfg)
        text = adapter.generate_rules(_sections("Code Style", "Testing"))
        assert text.startswith("---\n")
        assert "alwaysApply: true" in text
        assert "## Code Style" in text
        assert "## Testing" in text

    def test_md_format(self, tmp_path: Path):
        tc, cfg = _config(tmp_path, rules_format="md")
        adapter = CursorTargetAdapter(tc, cfg)
        text = adapter.generate_rules(_sections("Code Style"))
        assert not text.startswith("---")
        assert "## Code Style" in text

    def test_empty_sections(self, tmp_path: Path):
        tc, cfg = _config(tmp_path, rules_format="md")
        adapter = CursorTargetAdapter(tc, cfg)
        text = adapter.generate_rules([])
        assert text == ""


# ===================================================================
# write
# ===================================================================


class TestWrite:
    def test_write_mcp(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CursorTargetAdapter(tc, cfg)
        adapter.generate_mcp(_servers("a"))
        results = adapter.write()
        assert any(r.written for r in results)
        data = json.loads((tmp_path / "mcp.json").read_text())
        assert "a" in data["mcpServers"]

    def test_write_rules(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CursorTargetAdapter(tc, cfg)
        adapter.generate_rules(_sections("Code Style"))
        results = adapter.write()
        assert any(r.written for r in results)
        content = (tmp_path / "rules.mdc").read_text()
        assert "## Code Style" in content

    def test_dry_run(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CursorTargetAdapter(tc, cfg)
        adapter.generate_mcp(_servers("a"))
        adapter.generate_rules(_sections("Style"))
        results = adapter.write(dry_run=True)
        assert all(not r.written for r in results)
        assert not (tmp_path / "mcp.json").exists()

    def test_skip_if_not_generated(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CursorTargetAdapter(tc, cfg)
        results = adapter.write()
        assert results == []


# ===================================================================
# validate
# ===================================================================


class TestValidate:
    def test_consistent(self, tmp_path: Path):
        # Write a valid MCP file
        (tmp_path / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"a": {"command": "x"}, "b": {"command": "y"}}})
        )
        (tmp_path / "mcp.json").write_text(
            json.dumps({"mcpServers": {"a": {}, "b": {}}})
        )
        tc, cfg = _config(tmp_path)
        adapter = CursorTargetAdapter(tc, cfg)
        results = adapter.validate()
        server_check = [r for r in results if "consistency" in r.name]
        assert all(r.passed for r in server_check)

    def test_missing_server(self, tmp_path: Path):
        (tmp_path / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"a": {"command": "x"}, "b": {"command": "y"}}})
        )
        # Target only has "a", missing "b"
        (tmp_path / "mcp.json").write_text(
            json.dumps({"mcpServers": {"a": {}}})
        )
        tc, cfg = _config(tmp_path)
        adapter = CursorTargetAdapter(tc, cfg)
        results = adapter.validate()
        server_check = [r for r in results if "consistency" in r.name]
        assert any(not r.passed for r in server_check)

    def test_excluded_section_leak(self, tmp_path: Path):
        (tmp_path / "rules.mdc").write_text("## Secret\n\nDon't show this.\n")
        tc, cfg = _config(tmp_path, exclude_sections=["Secret"])
        adapter = CursorTargetAdapter(tc, cfg)
        results = adapter.validate()
        section_check = [r for r in results if "excluded" in r.name]
        assert any(not r.passed for r in section_check)

    def test_no_files(self, tmp_path: Path):
        tc, cfg = _config(tmp_path)
        adapter = CursorTargetAdapter(tc, cfg)
        results = adapter.validate()
        assert all(r.passed for r in results)
        assert all(r.severity == "info" for r in results)


# ===================================================================
# Integration: ClaudeSource → SyncEngine → CursorTarget
# ===================================================================


class TestIntegration:
    def test_full_cycle(self, tmp_path: Path):
        (tmp_path / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"ctx7": {"command": "npx", "args": ["-y", "@ctx7/mcp"]}}})
        )
        (tmp_path / "CLAUDE.md").write_text(
            "# Rules\n\n## Style\n\nUse snake_case.\n\n## Testing\n\nWrite tests.\n"
        )

        tc, cfg = _config(tmp_path)

        from agentsync.adapters.claude import ClaudeSourceAdapter

        source = ClaudeSourceAdapter(cfg)
        target = CursorTargetAdapter(tc, cfg)
        engine = SyncEngine(cfg, source, {"cursor": target})
        result = engine.run(dry_run=True)

        assert result.success is True
