"""Tests for agentsync.utils.io — write_json and write_text."""

from __future__ import annotations

from pathlib import Path

from agentsync.utils.io import write_json, write_text
from agentsync.utils.logger import SilentLogger


def _log() -> SilentLogger:
    return SilentLogger()


# === write_text ===


def test_write_text_creates_file(tmp_path: Path):
    target = tmp_path / "out.txt"
    wr = write_text(target, "hello\n", _log())
    assert wr.written is True
    assert target.read_text() == "hello\n"
    assert wr.bytes_written > 0


def test_write_text_dry_run(tmp_path: Path):
    target = tmp_path / "out.txt"
    wr = write_text(target, "hello\n", _log(), dry_run=True)
    assert wr.written is False
    assert not target.exists()


def test_write_text_no_change(tmp_path: Path):
    target = tmp_path / "out.txt"
    target.write_text("same\n")
    wr = write_text(target, "same\n", _log(), dry_run=True)
    assert "no changes" in wr.message


def test_write_text_with_backup(tmp_path: Path):
    target = tmp_path / "out.txt"
    target.write_text("old\n")
    backup_dir = tmp_path / "backups"
    wr = write_text(target, "new\n", _log(), backup_dir=backup_dir)
    assert wr.written is True
    assert target.read_text() == "new\n"
    assert list(backup_dir.glob("*.bak"))


# === write_json ===


def test_write_json_creates_file(tmp_path: Path):
    target = tmp_path / "out.json"
    wr = write_json(target, {"key": "value"}, _log())
    assert wr.written is True
    import json
    assert json.loads(target.read_text()) == {"key": "value"}


def test_write_json_dry_run(tmp_path: Path):
    target = tmp_path / "out.json"
    wr = write_json(target, {"a": 1}, _log(), dry_run=True)
    assert wr.written is False
    assert not target.exists()


def test_write_text_creates_parent_dirs(tmp_path: Path):
    target = tmp_path / "deep" / "nested" / "file.txt"
    wr = write_text(target, "content\n", _log())
    assert wr.written is True
    assert target.read_text() == "content\n"
