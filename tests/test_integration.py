"""Integration tests — full pipeline with real adapters and fixtures."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agentsync.cli import create_source, create_targets
from agentsync.config import (
    AgentSyncConfig,
    RulesConfig,
    SourceConfig,
    SyncOptions,
    TargetConfig,
    load_config,
)
from agentsync.sync import SyncEngine
from agentsync.validate import Validator

FIXTURES = Path(__file__).parent / "fixtures"


# ===================================================================
# Helpers
# ===================================================================


def _setup_project(tmp_path: Path) -> AgentSyncConfig:
    """Copy fixtures to a temp dir and build a config pointing there."""
    # Copy fixture files
    for name in ("claude_global.json", "claude_project_mcp.json", "claude_md_sample.md"):
        shutil.copy(FIXTURES / name, tmp_path / name)

    return AgentSyncConfig(
        version=1,
        source=SourceConfig(
            type="claude",
            global_config=str(tmp_path / "claude_global.json"),
            project_mcp=str(tmp_path / "claude_project_mcp.json"),
            rules_file=str(tmp_path / "claude_md_sample.md"),
        ),
        targets={
            "cursor": TargetConfig(
                type="cursor",
                mcp_path=str(tmp_path / "output" / "cursor_mcp.json"),
                rules_path=str(tmp_path / "output" / "cursor_rules.mdc"),
                rules_format="mdc",
            ),
            "codex": TargetConfig(
                type="codex",
                config_path=str(tmp_path / "output" / "codex_config.toml"),
                rules_path=str(tmp_path / "output" / "AGENTS.md"),
                rules_format="md",
                exclude_servers=["codex"],
            ),
            "antigravity": TargetConfig(
                type="antigravity",
                mcp_path=str(tmp_path / "output" / "antigravity_mcp.json"),
                protocols=["stdio"],
            ),
        },
        rules=RulesConfig(exclude_sections=["MCP Servers"]),
        sync=SyncOptions(backup=False),
        config_dir=tmp_path,
    )


# ===================================================================
# Full sync pipeline
# ===================================================================


def test_full_sync_pipeline(tmp_path: Path):
    """Source → dedup → generate → write for all targets."""
    cfg = _setup_project(tmp_path)
    source = create_source(cfg)
    targets = create_targets(cfg)

    engine = SyncEngine(cfg, source, targets)
    result = engine.run()

    assert result.success is True
    assert result.dry_run is False

    # All three targets processed
    assert set(result.target_results) == {"cursor", "codex", "antigravity"}

    # Cursor: MCP JSON should exist with servers
    cursor_mcp = tmp_path / "output" / "cursor_mcp.json"
    assert cursor_mcp.is_file()
    data = json.loads(cursor_mcp.read_text())
    assert "mcpServers" in data
    assert len(data["mcpServers"]) > 0

    # Cursor: rules MDC should exist
    cursor_rules = tmp_path / "output" / "cursor_rules.mdc"
    assert cursor_rules.is_file()
    content = cursor_rules.read_text()
    assert "---" in content  # MDC frontmatter
    assert "Behaviour Rules" in content
    # MCP Servers section should be excluded
    assert "## MCP Servers" not in content

    # Codex: config.toml with markers
    codex_toml = tmp_path / "output" / "codex_config.toml"
    assert codex_toml.is_file()
    toml_content = codex_toml.read_text()
    assert "AGENTSYNC START" in toml_content
    assert "AGENTSYNC END" in toml_content
    assert "mcp_servers." in toml_content

    # Codex: AGENTS.md should exist
    agents_md = tmp_path / "output" / "AGENTS.md"
    assert agents_md.is_file()

    # Antigravity: only stdio servers (no browsermcp which is HTTP)
    ag_mcp = tmp_path / "output" / "antigravity_mcp.json"
    assert ag_mcp.is_file()
    ag_data = json.loads(ag_mcp.read_text())
    ag_servers = ag_data.get("mcpServers", {})
    # browsermcp is HTTP — should be filtered out
    assert "browsermcp" not in ag_servers


def test_dry_run_no_files(tmp_path: Path):
    """Dry-run should NOT create any output files."""
    cfg = _setup_project(tmp_path)
    source = create_source(cfg)
    targets = create_targets(cfg)

    engine = SyncEngine(cfg, source, targets)
    result = engine.run(dry_run=True)

    assert result.success is True
    assert result.dry_run is True

    output_dir = tmp_path / "output"
    if output_dir.exists():
        assert list(output_dir.iterdir()) == []
    else:
        pass  # dir not created = correct


def test_mcp_only_skips_rules(tmp_path: Path):
    """--mcp-only should write MCP configs but no rules files."""
    cfg = _setup_project(tmp_path)
    source = create_source(cfg)
    targets = create_targets(cfg)

    engine = SyncEngine(cfg, source, targets)
    result = engine.run(mcp_only=True)

    assert result.success is True

    # MCP files should exist
    assert (tmp_path / "output" / "cursor_mcp.json").is_file()

    # Rules files should NOT exist
    assert not (tmp_path / "output" / "cursor_rules.mdc").is_file()
    assert not (tmp_path / "output" / "AGENTS.md").is_file()


def test_rules_only_skips_mcp(tmp_path: Path):
    """--rules-only should write rules but no MCP configs."""
    cfg = _setup_project(tmp_path)
    source = create_source(cfg)
    targets = create_targets(cfg)

    engine = SyncEngine(cfg, source, targets)
    result = engine.run(rules_only=True)

    assert result.success is True

    # MCP files should NOT exist
    assert not (tmp_path / "output" / "cursor_mcp.json").is_file()
    assert not (tmp_path / "output" / "antigravity_mcp.json").is_file()

    # Rules should exist
    assert (tmp_path / "output" / "cursor_rules.mdc").is_file()
    assert (tmp_path / "output" / "AGENTS.md").is_file()


# ===================================================================
# Validate pipeline
# ===================================================================


def test_sync_then_validate(tmp_path: Path):
    """Write → validate → all checks should pass."""
    cfg = _setup_project(tmp_path)
    source = create_source(cfg)
    targets = create_targets(cfg)

    # First sync
    engine = SyncEngine(cfg, source, targets)
    sync_result = engine.run()
    assert sync_result.success is True

    # Then validate — need fresh targets that will read written files
    targets2 = create_targets(cfg)
    validator = Validator(cfg, source, targets2)
    report = validator.run()

    assert report.passed is True
    assert len(report.results) > 0


def test_validate_target_filter(tmp_path: Path):
    """Validate with --target should only check that target."""
    cfg = _setup_project(tmp_path)
    source = create_source(cfg)
    targets = create_targets(cfg)

    # Sync first
    engine = SyncEngine(cfg, source, targets)
    engine.run()

    # Validate only cursor
    targets2 = create_targets(cfg)
    validator = Validator(cfg, source, targets2)
    report = validator.run(target_filter="cursor")

    assert report.passed is True
    # Should only have cursor-related results
    for r in report.results:
        assert "cursor" in r.name.lower() or r.passed


# ===================================================================
# Config loading from fixture
# ===================================================================


def test_load_fixture_config():
    """agentsync_config.yaml fixture should load successfully."""
    cfg = load_config(FIXTURES / "agentsync_config.yaml")
    assert cfg.version == 1
    assert cfg.source.type == "claude"
    assert "cursor" in cfg.targets
    assert "codex" in cfg.targets
    assert "antigravity" in cfg.targets
    assert cfg.rules.exclude_sections == ["MCP Servers"]
    assert cfg.sync.backup is False


def test_codex_preserves_existing_config(tmp_path: Path):
    """Codex adapter should preserve non-MCP sections in existing config.toml."""
    cfg = _setup_project(tmp_path)

    # Pre-populate codex config with existing content
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    existing_toml = output_dir / "codex_config.toml"
    shutil.copy(FIXTURES / "codex_config.toml", existing_toml)

    source = create_source(cfg)
    targets = create_targets(cfg)

    engine = SyncEngine(cfg, source, targets)
    result = engine.run()

    assert result.success is True

    final = existing_toml.read_text()
    # Original content preserved
    assert "[user]" in final
    assert 'name = "test-user"' in final
    assert "[settings]" in final
    # Managed block added
    assert "AGENTSYNC START" in final
    assert "AGENTSYNC END" in final
