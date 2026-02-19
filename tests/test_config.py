"""Tests for agentsync config loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentsync.config import (
    AgentSyncConfig,
    ConfigError,
    find_config,
    generate_default_config,
    load_config,
    resolve_path,
)


# === resolve_path ===


def test_resolve_tilde():
    result = resolve_path("~/test", Path("/base"))
    assert result == Path.home() / "test"


def test_resolve_relative():
    result = resolve_path("foo/bar", Path("/base"))
    assert result == Path("/base/foo/bar")


def test_resolve_absolute():
    result = resolve_path("/absolute/path", Path("/base"))
    assert result == Path("/absolute/path")


# === find_config ===


def test_find_config_in_current(tmp_path: Path):
    config = tmp_path / "agentsync.yaml"
    config.write_text("version: 1")
    assert find_config(tmp_path) == config


def test_find_config_in_parent(tmp_path: Path):
    config = tmp_path / "agentsync.yaml"
    config.write_text("version: 1")
    child = tmp_path / "sub" / "dir"
    child.mkdir(parents=True)
    assert find_config(child) == config


def test_find_config_not_found(tmp_path: Path):
    # Create a deep nested path where no agentsync.yaml exists
    # find_config walks up, so it may find one in real parent dirs
    # We test the walk-up terminates without error
    child = tmp_path / "a" / "b" / "c"
    child.mkdir(parents=True)
    result = find_config(child)
    # Result is either None (no config anywhere) or a real config file
    # The key assertion: it doesn't find one inside our tmp_path
    assert result is None or not str(result).startswith(str(tmp_path))


# === load_config ===


MINIMAL_CONFIG = """\
version: 1
targets:
  cursor:
    type: cursor
    mcp_path: ~/.cursor/mcp.json
"""


def test_load_minimal(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text(MINIMAL_CONFIG)
    config = load_config(config_file)

    assert isinstance(config, AgentSyncConfig)
    assert config.version == 1
    assert config.source.type == "claude"
    assert "cursor" in config.targets
    assert config.targets["cursor"].type == "cursor"
    assert config.targets["cursor"].mcp_path == "~/.cursor/mcp.json"


FULL_CONFIG = """\
version: 1

source:
  type: claude
  global_config: ~/.claude.json
  project_mcp: .mcp.json
  rules_file: CLAUDE.md

targets:
  cursor:
    type: cursor
    mcp_path: ~/.cursor/mcp.json
    rules_path: .cursor/rules/project.mdc
    rules_format: mdc
    exclude_servers: []

  codex:
    type: codex
    config_path: ~/.codex/config.toml
    rules_path: AGENTS.md
    rules_format: md
    exclude_servers:
      - codex

  antigravity:
    type: antigravity
    mcp_path: ~/.gemini/antigravity/mcp_config.json
    protocols:
      - stdio
    exclude_servers: []

rules:
  exclude_sections:
    - "MCP Servers"
    - "Context Management"

sync:
  backup: true
  backup_dir: .agentsync/backups
  log_dir: .agentsync/logs
"""


def test_load_full(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text(FULL_CONFIG)
    config = load_config(config_file)

    assert config.version == 1
    assert len(config.targets) == 3
    assert config.targets["codex"].exclude_servers == ["codex"]
    assert config.targets["antigravity"].protocols == ["stdio"]
    assert config.rules.exclude_sections == ["MCP Servers", "Context Management"]
    assert config.sync.backup is True
    assert config.config_dir == tmp_path.resolve()


def test_load_missing_file(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_invalid_yaml(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text(": invalid: yaml: [")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(config_file)


def test_load_missing_version(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text("targets:\n  x:\n    type: cursor\n")
    with pytest.raises(ConfigError, match="Missing required field 'version'"):
        load_config(config_file)


def test_load_unsupported_version(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text("version: 99\ntargets:\n  x:\n    type: cursor\n")
    with pytest.raises(ConfigError, match="Unsupported config version"):
        load_config(config_file)


def test_load_unknown_source_type(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text("version: 1\nsource:\n  type: unknown\ntargets:\n  x:\n    type: cursor\n")
    with pytest.raises(ConfigError, match="Unknown source type"):
        load_config(config_file)


def test_load_unknown_target_type(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text("version: 1\ntargets:\n  x:\n    type: unknown\n")
    with pytest.raises(ConfigError, match="unknown type 'unknown'"):
        load_config(config_file)


def test_load_missing_target_type(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text("version: 1\ntargets:\n  x:\n    mcp_path: foo\n")
    with pytest.raises(ConfigError, match="missing required field 'type'"):
        load_config(config_file)


def test_load_no_targets(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text("version: 1\ntargets: {}\n")
    with pytest.raises(ConfigError, match="At least one target"):
        load_config(config_file)


def test_load_invalid_rules_format(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text(
        "version: 1\ntargets:\n  x:\n    type: cursor\n    rules_format: html\n"
    )
    with pytest.raises(ConfigError, match="rules_format must be"):
        load_config(config_file)


def test_load_string_version(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text('version: "1"\ntargets:\n  x:\n    type: cursor\n')
    with pytest.raises(ConfigError, match="must be an integer"):
        load_config(config_file)


def test_load_non_bool_backup(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text(
        "version: 1\ntargets:\n  x:\n    type: cursor\nsync:\n  backup: yes_please\n"
    )
    with pytest.raises(ConfigError, match="must be a boolean"):
        load_config(config_file)


def test_load_non_string_exclude_servers(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text(
        "version: 1\ntargets:\n  x:\n    type: cursor\n    exclude_servers:\n      - 123\n"
    )
    with pytest.raises(ConfigError, match="exclude_servers must be a list of strings"):
        load_config(config_file)


def test_load_non_string_protocols(tmp_path: Path):
    config_file = tmp_path / "agentsync.yaml"
    config_file.write_text(
        "version: 1\ntargets:\n  x:\n    type: cursor\n    protocols:\n      - 123\n"
    )
    with pytest.raises(ConfigError, match="protocols must be a list of strings"):
        load_config(config_file)


# === generate_default_config ===


def test_generate_default(tmp_path: Path):
    path = generate_default_config(tmp_path)
    assert path.exists()
    assert "version: 1" in path.read_text()
    # Verify it's actually parseable
    config = load_config(path)
    assert config.version == 1
    assert len(config.targets) == 3


def test_generate_no_overwrite(tmp_path: Path):
    generate_default_config(tmp_path)
    with pytest.raises(ConfigError, match="already exists"):
        generate_default_config(tmp_path)


def test_generate_force_overwrite(tmp_path: Path):
    generate_default_config(tmp_path)
    path = generate_default_config(tmp_path, force=True)
    assert path.exists()
