"""Tests for agentsync.utils.backup — file backup utility."""

from __future__ import annotations

from pathlib import Path

from agentsync.utils.backup import backup_file
from agentsync.utils.logger import SilentLogger


def _log() -> SilentLogger:
    return SilentLogger()


def test_backup_creates_copy(tmp_path: Path):
    source = tmp_path / "original.json"
    source.write_text('{"a":1}')
    backup_dir = tmp_path / "backups"

    result = backup_file(source, backup_dir, _log())

    assert result is not None
    assert result.exists()
    assert result.read_text() == '{"a":1}'
    assert result.suffix == ".bak"


def test_backup_nonexistent_returns_none(tmp_path: Path):
    source = tmp_path / "missing.txt"
    result = backup_file(source, tmp_path / "backups", _log())
    assert result is None


def test_backup_creates_dir(tmp_path: Path):
    source = tmp_path / "file.txt"
    source.write_text("data")
    backup_dir = tmp_path / "new" / "backup" / "dir"

    result = backup_file(source, backup_dir, _log())

    assert result is not None
    assert backup_dir.exists()
