"""Tests for agentsync.utils.dedup — case-insensitive server deduplication."""

from __future__ import annotations

from agentsync.adapters.base import ServerConfig
from agentsync.utils.dedup import dedup_servers
from agentsync.utils.logger import SilentLogger


def _sc(name: str, **extra: object) -> ServerConfig:
    return ServerConfig(name=name, config={"command": "test", **extra})


def _log() -> SilentLogger:
    return SilentLogger()


def test_no_duplicates():
    servers = {"alpha": _sc("alpha"), "beta": _sc("beta")}
    result = dedup_servers(servers, _log())
    assert set(result) == {"alpha", "beta"}


def test_case_insensitive_dedup():
    servers = {"Notion": _sc("Notion"), "notion": _sc("notion")}
    result = dedup_servers(servers, _log())
    assert len(result) == 1
    assert "notion" in result


def test_later_entry_wins():
    s1 = ServerConfig(name="A", config={"command": "old"})
    s2 = ServerConfig(name="a", config={"command": "new"})
    result = dedup_servers({"A": s1, "a": s2}, _log())
    assert result["a"].config["command"] == "new"


def test_keys_lowercased():
    servers = {"GitHub": _sc("GitHub"), "Linear": _sc("Linear")}
    result = dedup_servers(servers, _log())
    assert set(result) == {"github", "linear"}


def test_empty_input():
    result = dedup_servers({}, _log())
    assert result == {}
