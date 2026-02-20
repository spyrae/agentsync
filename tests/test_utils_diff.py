"""Tests for agentsync.utils.diff — server diff display."""

from __future__ import annotations

import json
from pathlib import Path

from agentsync.adapters.base import ServerConfig
from agentsync.utils.diff import show_server_diff
from agentsync.utils.logger import SyncLogger


def _servers(*names: str) -> dict[str, ServerConfig]:
    return {n: ServerConfig(name=n, config={"command": "test"}) for n in names}


def test_no_existing_file(tmp_path: Path):
    log = SyncLogger(quiet=True)
    show_server_diff("target", tmp_path / "missing.json", _servers("a", "b"), log)
    assert any("doesn't exist" in line for line in log._buffer)


def test_servers_added(tmp_path: Path):
    existing = tmp_path / "mcp.json"
    existing.write_text(json.dumps({"mcpServers": {"a": {}}}))
    log = SyncLogger(quiet=True)
    show_server_diff("target", existing, _servers("a", "b"), log)
    assert any("+1 server" in line for line in log._buffer)


def test_servers_removed(tmp_path: Path):
    existing = tmp_path / "mcp.json"
    existing.write_text(json.dumps({"mcpServers": {"a": {}, "b": {}, "c": {}}}))
    log = SyncLogger(quiet=True)
    show_server_diff("target", existing, _servers("a"), log)
    assert any("-2 servers" in line for line in log._buffer)


def test_no_diff(tmp_path: Path):
    existing = tmp_path / "mcp.json"
    existing.write_text(json.dumps({"mcpServers": {"a": {}, "b": {}}}))
    log = SyncLogger(quiet=True)
    show_server_diff("target", existing, _servers("a", "b"), log)
    assert any("same 2 servers" in line for line in log._buffer)


def test_invalid_json(tmp_path: Path):
    existing = tmp_path / "mcp.json"
    existing.write_text("not json at all")
    log = SyncLogger(quiet=True)
    show_server_diff("target", existing, _servers("a"), log)
    # Should treat existing as empty → all servers are "added"
    assert any("+1 server" in line for line in log._buffer)


def test_added_and_removed(tmp_path: Path):
    existing = tmp_path / "mcp.json"
    existing.write_text(json.dumps({"mcpServers": {"old": {}}}))
    log = SyncLogger(quiet=True)
    show_server_diff("target", existing, _servers("new"), log)
    assert any("+1" in line for line in log._buffer)
    assert any("-1" in line for line in log._buffer)
