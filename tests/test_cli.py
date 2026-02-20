"""Tests for agentsync CLI — commands, exit codes, output."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agentsync.adapters.base import (
    Section,
    ServerConfig,
    SourceAdapter,
    TargetAdapter,
    ValidationResult,
    WriteResult,
)
from agentsync.cli import EXIT_CONFIG_ERROR, EXIT_OK, EXIT_RUNTIME_ERROR, main
from agentsync.config import CONFIG_FILENAME

# ===================================================================
# Fake adapters for CLI tests
# ===================================================================


class FakeSource(SourceAdapter):
    def __init__(self, servers: dict[str, ServerConfig] | None = None) -> None:
        self._servers = servers or {
            "s1": ServerConfig(name="s1", config={"command": "test"}),
            "s2": ServerConfig(name="s2", config={"command": "test2"}),
        }

    def load_servers(self) -> dict[str, ServerConfig]:
        return dict(self._servers)

    def load_rules(self) -> list[Section]:
        return [Section(header="Rules", level=2, content="## Rules\nSome rules")]


@dataclass
class FakeTarget(TargetAdapter):
    name: str = "fake"
    write_results: list[WriteResult] = field(default_factory=list)
    validation_results: list[ValidationResult] = field(default_factory=list)

    def generate_mcp(self, servers: dict[str, ServerConfig]) -> dict[str, Any]:
        return {"mcpServers": {k: v.config for k, v in servers.items()}}

    def generate_rules(self, sections: list[Section]) -> str:
        return "\n".join(s.content for s in sections)

    def write(self, dry_run: bool = False) -> list[WriteResult]:
        if dry_run:
            return [WriteResult(path="fake.json", written=False, message="WOULD CREATE")]
        return self.write_results or [
            WriteResult(path="fake.json", written=True, bytes_written=100),
        ]

    def validate(self) -> list[ValidationResult]:
        return self.validation_results or [
            ValidationResult(name="fake check", passed=True, message="ok"),
        ]


# ===================================================================
# Helpers
# ===================================================================

MINIMAL_CONFIG = """\
version: 1
targets:
  cursor:
    type: cursor
"""


def _write_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    cfg = tmp_path / CONFIG_FILENAME
    cfg.write_text(content)
    return cfg


def _patch_adapters(source=None, targets=None):
    """Return a pair of patch context managers for create_source and create_targets."""
    src = source or FakeSource()
    tgts = targets or {"cursor": FakeTarget(name="cursor")}
    return (
        patch("agentsync.cli.create_source", return_value=src),
        patch("agentsync.cli.create_targets", return_value=tgts),
    )


# ===================================================================
# Tests — version and help
# ===================================================================


def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == EXIT_OK
    assert "agentsync" in result.output
    assert "0.1.0" in result.output


def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == EXIT_OK
    assert "sync" in result.output
    assert "validate" in result.output
    assert "init" in result.output
    assert "status" in result.output


@pytest.mark.parametrize("cmd", ["sync", "validate", "init", "status"])
def test_subcommand_help(cmd: str):
    runner = CliRunner()
    result = runner.invoke(main, [cmd, "--help"])
    assert result.exit_code == EXIT_OK
    assert cmd in result.output.lower() or "--help" in result.output


# ===================================================================
# Tests — init
# ===================================================================


def test_init_creates_file(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        result = runner.invoke(main, ["init"])
        assert result.exit_code == EXIT_OK
        assert "Created" in result.output
        assert (Path(td) / CONFIG_FILENAME).is_file()


def test_init_no_overwrite(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        (Path(td) / CONFIG_FILENAME).write_text("existing")
        result = runner.invoke(main, ["init"])
        assert result.exit_code == EXIT_CONFIG_ERROR
        assert "already exists" in result.output


def test_init_force(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        (Path(td) / CONFIG_FILENAME).write_text("old content")
        result = runner.invoke(main, ["init", "--force"])
        assert result.exit_code == EXIT_OK
        assert "Created" in result.output
        content = (Path(td) / CONFIG_FILENAME).read_text()
        assert "version: 1" in content


# ===================================================================
# Tests — sync
# ===================================================================


def test_sync_no_config(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["sync"])
        assert result.exit_code == EXIT_CONFIG_ERROR
        assert "Error" in result.output


def test_sync_dry_run(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    p_src, p_tgt = _patch_adapters()
    with p_src, p_tgt:
        result = runner.invoke(main, ["-c", str(cfg_path), "sync", "--dry-run"])
    assert result.exit_code == EXIT_OK
    assert "DRY RUN" in result.output


def test_sync_full(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    target = FakeTarget(
        name="cursor",
        write_results=[WriteResult(path="mcp.json", written=True, bytes_written=200)],
    )
    p_src, p_tgt = _patch_adapters(targets={"cursor": target})
    with p_src, p_tgt:
        result = runner.invoke(main, ["-c", str(cfg_path), "sync"])
    assert result.exit_code == EXIT_OK
    assert "Sync complete" in result.output


def test_sync_mcp_only(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    p_src, p_tgt = _patch_adapters()
    with p_src, p_tgt:
        result = runner.invoke(main, ["-c", str(cfg_path), "sync", "--mcp-only"])
    assert result.exit_code == EXIT_OK


def test_sync_target_filter(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    p_src, p_tgt = _patch_adapters()
    with p_src, p_tgt:
        result = runner.invoke(main, ["-c", str(cfg_path), "sync", "-t", "cursor"])
    assert result.exit_code == EXIT_OK


def test_sync_no_backup_flag(tmp_path: Path):
    """--no-backup should disable backup in the config."""
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    captured_cfg = {}

    def patched_engine_init(self, config, source, targets):
        captured_cfg["backup"] = config.sync.backup
        self._config = config
        self._source = source
        self._targets = targets

    p_src, p_tgt = _patch_adapters()
    with p_src, p_tgt, patch("agentsync.sync.SyncEngine.__init__", patched_engine_init):
        runner.invoke(main, ["-c", str(cfg_path), "sync", "--no-backup"])

    assert captured_cfg.get("backup") is False


# ===================================================================
# Tests — validate
# ===================================================================


def test_validate_no_config(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["validate"])
        assert result.exit_code == EXIT_CONFIG_ERROR


def test_validate_pass(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    target = FakeTarget(
        name="cursor",
        validation_results=[
            ValidationResult(name="check1", passed=True, message="all good"),
        ],
    )
    p_src, p_tgt = _patch_adapters(targets={"cursor": target})
    with p_src, p_tgt:
        result = runner.invoke(main, ["-c", str(cfg_path), "validate", "-v"])
    assert result.exit_code == EXIT_OK
    assert "passed" in result.output


def test_validate_fail(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    target = FakeTarget(
        name="cursor",
        validation_results=[
            ValidationResult(name="check1", passed=False, message="mismatch", severity="error"),
        ],
    )
    p_src, p_tgt = _patch_adapters(targets={"cursor": target})
    with p_src, p_tgt:
        result = runner.invoke(main, ["-c", str(cfg_path), "validate"])
    assert result.exit_code == EXIT_RUNTIME_ERROR
    assert "failed" in result.output


# ===================================================================
# Tests — status
# ===================================================================


def test_status(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    p_src, p_tgt = _patch_adapters()
    with p_src, p_tgt:
        result = runner.invoke(main, ["-c", str(cfg_path), "status"])
    assert result.exit_code == EXIT_OK
    assert "Source" in result.output
    assert "Targets" in result.output


def test_status_no_config(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["status"])
        assert result.exit_code == EXIT_CONFIG_ERROR


# ===================================================================
# Tests — quiet mode
# ===================================================================


def test_quiet_sync(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    p_src, p_tgt = _patch_adapters()
    with p_src, p_tgt:
        result = runner.invoke(main, ["-q", "-c", str(cfg_path), "sync"])
    assert result.exit_code == EXIT_OK
    # quiet mode should suppress the summary
    assert "Sync complete" not in result.output


def test_quiet_validate(tmp_path: Path):
    runner = CliRunner()
    cfg_path = _write_config(tmp_path)
    p_src, p_tgt = _patch_adapters()
    with p_src, p_tgt:
        result = runner.invoke(main, ["-q", "-c", str(cfg_path), "validate"])
    assert result.exit_code == EXIT_OK
    assert "Validation" not in result.output
