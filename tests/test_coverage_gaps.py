"""Tests covering specific coverage gaps in logger, io, output modules."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from agentsync.adapters.base import (
    ServerConfig,
    ValidationResult,
    WriteResult,
)
from agentsync.config import (
    AgentSyncConfig,
    SourceConfig,
    TargetConfig,
)
from agentsync.sync import SyncResult, TargetSyncResult
from agentsync.utils.logger import SyncLogger
from agentsync.utils.output import print_status, print_sync_summary, print_validation_report
from agentsync.validate import ValidationReport

# ===================================================================
# Logger — flush_to_file
# ===================================================================


def test_logger_flush_to_file(tmp_path: Path):
    log = SyncLogger(quiet=True)
    log.info("test message 1")
    log.warn("warning message")
    log.error("error message")

    log_dir = tmp_path / "logs"
    log.flush_to_file(log_dir)

    assert log_dir.is_dir()
    log_files = list(log_dir.glob("sync-*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text()
    assert "test message 1" in content
    assert "warning message" in content
    assert "error message" in content


def test_logger_flush_empty_buffer(tmp_path: Path):
    """Flushing with no messages should not create a file."""
    log = SyncLogger(quiet=True)
    log_dir = tmp_path / "logs"
    log.flush_to_file(log_dir)
    assert not log_dir.exists()


def test_logger_section(tmp_path: Path):
    log = SyncLogger(quiet=True)
    log.section("Test Section")
    assert any("Test Section" in line for line in log._buffer)


def test_logger_dry_run_prefix():
    log = SyncLogger(dry_run=True, quiet=True)
    log.info("msg")
    assert any("[DRY-RUN]" in line for line in log._buffer)


# ===================================================================
# IO — write_json with backup
# ===================================================================


def test_write_json_with_backup(tmp_path: Path):
    from agentsync.utils.io import write_json

    log = SyncLogger(quiet=True)
    target = tmp_path / "test.json"
    target.write_text('{"old": true}\n')

    backup_dir = tmp_path / "backups"
    result = write_json(target, {"new": True}, log, backup_dir=backup_dir, dry_run=False)

    assert result.written is True
    data = json.loads(target.read_text())
    assert data == {"new": True}
    # Backup should have been created
    backups = list(backup_dir.rglob("*.json*"))
    assert len(backups) >= 1


def test_write_text_dry_run_no_change(tmp_path: Path):
    from agentsync.utils.io import write_text

    log = SyncLogger(quiet=True)
    target = tmp_path / "test.txt"
    target.write_text("same content")

    result = write_text(target, "same content", log, dry_run=True)
    assert result.written is False
    assert "no changes" in result.message


def test_write_text_dry_run_update(tmp_path: Path):
    from agentsync.utils.io import write_text

    log = SyncLogger(quiet=True)
    target = tmp_path / "test.txt"
    target.write_text("old content")

    result = write_text(target, "new content", log, dry_run=True)
    assert result.written is False
    assert "WOULD UPDATE" in result.message


# ===================================================================
# Output — sync summary edge cases
# ===================================================================


def test_sync_summary_with_errors():
    console = Console(quiet=True)
    result = SyncResult(
        success=False,
        dry_run=False,
        target_results={
            "cursor": TargetSyncResult(
                target_name="cursor",
                success=True,
                writes=[WriteResult(path="a.json", written=True, bytes_written=100)],
            ),
            "codex": TargetSyncResult(
                target_name="codex",
                success=False,
                errors=["write failed: permission denied"],
            ),
        },
    )
    # Should not raise
    print_sync_summary(result, console=console)


def test_sync_summary_dry_run():
    result = SyncResult(
        success=True,
        dry_run=True,
        target_results={
            "cursor": TargetSyncResult(
                target_name="cursor",
                success=True,
                writes=[WriteResult(path="a.json", written=False, message="WOULD CREATE")],
            ),
        },
    )
    # Should not raise
    print_sync_summary(result, console=Console(quiet=True))


def test_sync_summary_single_file():
    """Test singular 'file' vs plural 'files' in output."""
    console = Console(quiet=True)
    result = SyncResult(
        success=True,
        dry_run=False,
        target_results={
            "t1": TargetSyncResult(
                target_name="t1",
                success=True,
                writes=[WriteResult(path="a.json", written=True, bytes_written=50)],
            ),
        },
    )
    print_sync_summary(result, console=console)


# ===================================================================
# Output — validation report edge cases
# ===================================================================


def test_validation_report_verbose():
    console = Console(quiet=True)
    report = ValidationReport(
        passed=True,
        results=[
            ValidationResult(name="check1", passed=True, message="all ok"),
            ValidationResult(name="check2", passed=True, message="great"),
        ],
    )
    # verbose=True should show all
    print_validation_report(report, verbose=True, console=console)


def test_validation_report_failures_only():
    console = Console(quiet=True)
    report = ValidationReport(
        passed=False,
        results=[
            ValidationResult(name="check1", passed=True, message="ok"),
            ValidationResult(name="check2", passed=False, message="bad"),
        ],
    )
    # verbose=False should only show failures
    print_validation_report(report, verbose=False, console=console)


# ===================================================================
# Output — status with missing source files
# ===================================================================


def test_status_missing_source_files(tmp_path: Path):
    """Status should handle missing source files gracefully."""
    from unittest.mock import MagicMock

    console = Console(quiet=True)
    cfg = AgentSyncConfig(
        source=SourceConfig(
            global_config=str(tmp_path / "nonexistent_global.json"),
            project_mcp=str(tmp_path / "nonexistent_mcp.json"),
            rules_file=str(tmp_path / "nonexistent.md"),
        ),
        targets={"t1": TargetConfig(type="cursor")},
        config_dir=tmp_path,
    )

    source = MagicMock()
    source.load_servers.return_value = {}

    target = MagicMock()
    target.validate.return_value = []

    print_status(cfg, source, {"t1": target}, console=console)


def test_status_existing_source_files(tmp_path: Path):
    """Status should show server count for existing source files."""
    from unittest.mock import MagicMock

    console = Console(quiet=True)

    # Create source files
    global_cfg = tmp_path / "global.json"
    global_cfg.write_text('{"mcpServers": {}}')
    mcp_json = tmp_path / "mcp.json"
    mcp_json.write_text('{"mcpServers": {"s1": {}}}')
    rules = tmp_path / "CLAUDE.md"
    rules.write_text("# Rules")

    cfg = AgentSyncConfig(
        source=SourceConfig(
            global_config=str(global_cfg),
            project_mcp=str(mcp_json),
            rules_file=str(rules),
        ),
        targets={"t1": TargetConfig(type="cursor")},
        config_dir=tmp_path,
    )

    source = MagicMock()
    source.load_servers.return_value = {
        "s1": ServerConfig(name="s1", config={"command": "test"}),
    }

    target = MagicMock()
    target.validate.return_value = [
        ValidationResult(name="check", passed=True, message="ok"),
    ]

    print_status(cfg, source, {"t1": target}, console=console)


def test_status_target_validate_exception(tmp_path: Path):
    """Status should handle target.validate() throwing an exception."""
    from unittest.mock import MagicMock

    console = Console(quiet=True)
    cfg = AgentSyncConfig(
        source=SourceConfig(
            global_config=str(tmp_path / "x.json"),
            project_mcp=str(tmp_path / "y.json"),
            rules_file=str(tmp_path / "z.md"),
        ),
        targets={"t1": TargetConfig(type="cursor")},
        config_dir=tmp_path,
    )

    source = MagicMock()
    target = MagicMock()
    target.validate.side_effect = RuntimeError("boom")

    print_status(cfg, source, {"t1": target}, console=console)


def test_status_target_with_failures(tmp_path: Path):
    """Status should show failure count when validation fails."""
    from unittest.mock import MagicMock

    console = Console(quiet=True)
    cfg = AgentSyncConfig(
        source=SourceConfig(
            global_config=str(tmp_path / "x.json"),
            project_mcp=str(tmp_path / "y.json"),
            rules_file=str(tmp_path / "z.md"),
        ),
        targets={"t1": TargetConfig(type="cursor")},
        config_dir=tmp_path,
    )

    source = MagicMock()
    target = MagicMock()
    target.validate.return_value = [
        ValidationResult(name="ok", passed=True, message="ok"),
        ValidationResult(name="bad", passed=False, message="failed"),
    ]

    print_status(cfg, source, {"t1": target}, console=console)
