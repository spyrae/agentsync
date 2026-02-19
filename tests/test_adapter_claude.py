"""Tests for agentsync.adapters.claude — ClaudeSourceAdapter."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentsync.adapters.base import (
    Section,
    ServerConfig,
    TargetAdapter,
    ValidationResult,
    WriteResult,
)
from agentsync.adapters.claude import ClaudeSourceAdapter
from agentsync.config import AgentSyncConfig, SourceConfig, SyncOptions, TargetConfig
from agentsync.sync import SyncEngine

# ===================================================================
# Helpers
# ===================================================================


def _make_config(tmp_path: Path, **source_overrides: str) -> AgentSyncConfig:
    """Build an AgentSyncConfig rooted at tmp_path with custom source paths."""
    defaults = {
        "global_config": str(tmp_path / ".claude.json"),
        "project_mcp": str(tmp_path / ".mcp.json"),
        "rules_file": str(tmp_path / "CLAUDE.md"),
    }
    defaults.update(source_overrides)
    return AgentSyncConfig(
        source=SourceConfig(type="claude", **defaults),
        targets={"fake": TargetConfig(type="cursor")},
        sync=SyncOptions(),
        config_dir=tmp_path,
    )


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


@dataclass
class FakeTarget(TargetAdapter):
    generated_mcp: dict[str, ServerConfig] = field(default_factory=dict)
    generated_rules: list[Section] = field(default_factory=list)

    def generate_mcp(self, servers: dict[str, ServerConfig]) -> dict[str, Any]:
        self.generated_mcp = servers
        return {}

    def generate_rules(self, sections: list[Section]) -> str:
        self.generated_rules = sections
        return ""

    def write(self, dry_run: bool = False) -> list[WriteResult]:
        return []

    def validate(self) -> list[ValidationResult]:
        return []


# ===================================================================
# _read_json
# ===================================================================


class TestReadJson:
    def test_valid_json(self, tmp_path: Path):
        path = tmp_path / "test.json"
        _write_json(path, {"key": "value"})
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        assert adapter._read_json(path) == {"key": "value"}

    def test_missing_file_returns_none(self, tmp_path: Path):
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        assert adapter._read_json(tmp_path / "nope.json") is None

    def test_invalid_json_returns_none(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json!!!", encoding="utf-8")
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        assert adapter._read_json(path) is None

    def test_non_utf8_json_returns_none(self, tmp_path: Path):
        path = tmp_path / "binary.json"
        path.write_bytes(b"\xff\xfe{bad}")
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        assert adapter._read_json(path) is None


# ===================================================================
# _extract_servers
# ===================================================================


class TestExtractServers:
    def test_normal_extraction(self, tmp_path: Path):
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        raw = {
            "server-a": {"command": "npx", "args": ["-y", "pkg"]},
            "server-b": {"url": "https://example.com/mcp"},
        }
        result = adapter._extract_servers(raw)
        assert set(result) == {"server-a", "server-b"}
        assert result["server-a"].name == "server-a"
        assert result["server-a"].config["command"] == "npx"

    def test_empty_dict(self, tmp_path: Path):
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        assert adapter._extract_servers({}) == {}


# ===================================================================
# load_servers
# ===================================================================


class TestLoadServers:
    def test_global_only(self, tmp_path: Path):
        """Tier 1: top-level mcpServers from ~/.claude.json."""
        _write_json(tmp_path / ".claude.json", {
            "mcpServers": {
                "global-srv": {"command": "node", "args": ["server.js"]},
            }
        })
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert "global-srv" in servers

    def test_project_specific(self, tmp_path: Path):
        """Tier 2: project-specific mcpServers from ~/.claude.json projects block."""
        _write_json(tmp_path / ".claude.json", {
            "mcpServers": {},
            "projects": {
                str(tmp_path): {
                    "mcpServers": {
                        "project-srv": {"command": "deno", "args": ["run"]},
                    }
                }
            }
        })
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert "project-srv" in servers

    def test_local_mcp_json(self, tmp_path: Path):
        """Tier 3: .mcp.json servers."""
        _write_json(tmp_path / ".mcp.json", {
            "mcpServers": {
                "local-srv": {"url": "https://local.dev/mcp"},
            }
        })
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert "local-srv" in servers

    def test_three_tier_merge(self, tmp_path: Path):
        """All three tiers merge correctly."""
        _write_json(tmp_path / ".claude.json", {
            "mcpServers": {
                "global-only": {"command": "g"},
            },
            "projects": {
                str(tmp_path): {
                    "mcpServers": {
                        "project-only": {"command": "p"},
                    }
                }
            }
        })
        _write_json(tmp_path / ".mcp.json", {
            "mcpServers": {
                "local-only": {"command": "l"},
            }
        })
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert set(servers) == {"global-only", "project-only", "local-only"}

    def test_override_priority(self, tmp_path: Path):
        """Same server name on all tiers — .mcp.json (tier 3) wins."""
        _write_json(tmp_path / ".claude.json", {
            "mcpServers": {
                "shared": {"command": "global-cmd"},
            },
            "projects": {
                str(tmp_path): {
                    "mcpServers": {
                        "shared": {"command": "project-cmd"},
                    }
                }
            }
        })
        _write_json(tmp_path / ".mcp.json", {
            "mcpServers": {
                "shared": {"command": "local-cmd"},
            }
        })
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert servers["shared"].config["command"] == "local-cmd"

    def test_no_files_exist(self, tmp_path: Path):
        """No config files at all — returns empty, no errors."""
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert servers == {}

    def test_global_exists_no_mcp(self, tmp_path: Path):
        """Global config exists but .mcp.json doesn't."""
        _write_json(tmp_path / ".claude.json", {
            "mcpServers": {"srv": {"command": "x"}},
        })
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert "srv" in servers

    def test_mcp_exists_no_global(self, tmp_path: Path):
        """Only .mcp.json exists, no global config."""
        _write_json(tmp_path / ".mcp.json", {
            "mcpServers": {"local": {"url": "http://x"}},
        })
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert "local" in servers

    def test_mcp_servers_not_dict(self, tmp_path: Path):
        """mcpServers is a list instead of dict — no crash, empty result."""
        _write_json(tmp_path / ".mcp.json", {"mcpServers": ["wrong"]})
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert servers == {}

    def test_mcp_servers_null(self, tmp_path: Path):
        """mcpServers is null — no crash, empty result."""
        _write_json(tmp_path / ".mcp.json", {"mcpServers": None})
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        servers = adapter.load_servers()
        assert servers == {}


# ===================================================================
# load_rules
# ===================================================================


class TestLoadRules:
    def test_normal_rules(self, tmp_path: Path):
        md = "# Title\n\nPreamble\n\n## Section A\n\nContent A\n\n## Section B\n\nContent B\n"
        (tmp_path / "CLAUDE.md").write_text(md, encoding="utf-8")
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        sections = adapter.load_rules()
        assert len(sections) == 2
        assert sections[0].header == "Section A"
        assert sections[1].header == "Section B"

    def test_no_file(self, tmp_path: Path):
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        sections = adapter.load_rules()
        assert sections == []

    def test_empty_file(self, tmp_path: Path):
        (tmp_path / "CLAUDE.md").write_text("", encoding="utf-8")
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        sections = adapter.load_rules()
        assert sections == []

    def test_invalid_encoding(self, tmp_path: Path):
        """Non-UTF-8 file — returns empty list, no crash."""
        (tmp_path / "CLAUDE.md").write_bytes(b"\xff\xfe invalid \x80\x81")
        adapter = ClaudeSourceAdapter(_make_config(tmp_path))
        sections = adapter.load_rules()
        assert sections == []


# ===================================================================
# Integration: ClaudeSourceAdapter + SyncEngine
# ===================================================================


class TestIntegration:
    def test_full_cycle_with_sync_engine(self, tmp_path: Path):
        """ClaudeSourceAdapter feeds real data into SyncEngine with FakeTarget."""
        _write_json(tmp_path / ".mcp.json", {
            "mcpServers": {
                "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]},
                "supabase": {"url": "https://supa.co/mcp"},
            }
        })
        (tmp_path / "CLAUDE.md").write_text(
            "# Rules\n\n## Code Style\n\nUse snake_case.\n\n## Testing\n\nWrite tests.\n",
            encoding="utf-8",
        )

        cfg = AgentSyncConfig(
            source=SourceConfig(
                type="claude",
                global_config=str(tmp_path / ".claude.json"),
                project_mcp=str(tmp_path / ".mcp.json"),
                rules_file=str(tmp_path / "CLAUDE.md"),
            ),
            targets={"fake": TargetConfig(type="cursor")},
            config_dir=tmp_path,
        )

        source = ClaudeSourceAdapter(cfg)
        target = FakeTarget()
        engine = SyncEngine(cfg, source, {"fake": target})
        result = engine.run(dry_run=True)

        assert result.success is True
        assert "context7" in target.generated_mcp
        assert "supabase" in target.generated_mcp
        assert len(target.generated_rules) == 2

    def test_empty_source_no_crash(self, tmp_path: Path):
        """Empty source (no files) still produces a valid sync with empty data."""
        cfg = AgentSyncConfig(
            source=SourceConfig(
                type="claude",
                global_config=str(tmp_path / ".claude.json"),
                project_mcp=str(tmp_path / ".mcp.json"),
                rules_file=str(tmp_path / "CLAUDE.md"),
            ),
            targets={"fake": TargetConfig(type="cursor")},
            config_dir=tmp_path,
        )

        source = ClaudeSourceAdapter(cfg)
        target = FakeTarget()
        engine = SyncEngine(cfg, source, {"fake": target})
        result = engine.run(dry_run=True)

        assert result.success is True
        assert target.generated_mcp == {}
        assert target.generated_rules == []
