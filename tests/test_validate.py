"""Tests for agentsync.validate — standalone checks and Validator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentsync.adapters.base import (
    Section,
    ServerConfig,
    SourceAdapter,
    TargetAdapter,
    ValidationResult,
    WriteResult,
)
from agentsync.config import AgentSyncConfig, TargetConfig
from agentsync.validate import (
    Validator,
    check_case_insensitive_duplicates,
    check_no_excluded_sections,
    check_server_consistency,
)

# ===================================================================
# Helpers / fake adapters
# ===================================================================


def _sc(name: str, **extra: object) -> ServerConfig:
    return ServerConfig(name=name, config={"command": "test", **extra})


class FakeSource(SourceAdapter):
    def __init__(self, servers: dict[str, ServerConfig] | None = None) -> None:
        self._servers = servers or {}

    def load_servers(self) -> dict[str, ServerConfig]:
        return dict(self._servers)

    def load_rules(self) -> list[Section]:
        return []


@dataclass
class FakeTarget(TargetAdapter):
    validation_results: list[ValidationResult] = field(default_factory=list)
    raise_on_validate: bool = False

    def generate_mcp(self, servers: dict[str, ServerConfig]) -> dict[str, Any]:
        return {}

    def generate_rules(self, sections: list[Section]) -> str:
        return ""

    def write(self, dry_run: bool = False) -> list[WriteResult]:
        return []

    def validate(self) -> list[ValidationResult]:
        if self.raise_on_validate:
            raise RuntimeError("validation boom")
        return list(self.validation_results)


def _config(target_names: list[str] | None = None) -> AgentSyncConfig:
    names = target_names or ["t1"]
    targets = {n: TargetConfig(type="fake") for n in names}
    return AgentSyncConfig(targets=targets)


# ===================================================================
# Standalone check functions
# ===================================================================


def test_check_server_consistency_all_present():
    expected = {"a": _sc("a"), "b": _sc("b")}
    vr = check_server_consistency(expected, {"a", "b"}, "T", exclude=set())
    assert vr.passed is True


def test_check_server_consistency_missing():
    expected = {"a": _sc("a"), "b": _sc("b"), "c": _sc("c")}
    vr = check_server_consistency(expected, {"a"}, "T", exclude=set())
    assert vr.passed is False
    assert "missing" in vr.message


def test_check_server_consistency_with_exclude():
    expected = {"a": _sc("a"), "excluded": _sc("excluded")}
    vr = check_server_consistency(expected, {"a"}, "T", exclude={"excluded"})
    assert vr.passed is True


def test_check_server_consistency_stdio_only():
    expected = {
        "stdio": ServerConfig(name="stdio", config={"command": "x"}),
        "http": ServerConfig(name="http", config={"url": "http://x"}),
    }
    vr = check_server_consistency(expected, {"stdio"}, "T", exclude=set(), stdio_only=True)
    assert vr.passed is True


def test_check_no_excluded_sections_clean():
    content = "## Safe Section\nContent here.\n"
    vr = check_no_excluded_sections(content, {"Dangerous"}, "test")
    assert vr.passed is True


def test_check_no_excluded_sections_leaked():
    content = "## OK\nfoo\n## Dangerous\nbar\n"
    vr = check_no_excluded_sections(content, {"Dangerous"}, "test")
    assert vr.passed is False
    assert "Dangerous" in vr.message


def test_check_case_insensitive_duplicates_clean():
    vr = check_case_insensitive_duplicates(["alpha", "beta"], "test")
    assert vr.passed is True


def test_check_case_insensitive_duplicates_found():
    vr = check_case_insensitive_duplicates(["Alpha", "alpha"], "test")
    assert vr.passed is False


# ===================================================================
# Validator
# ===================================================================


def test_validator_all_pass():
    source = FakeSource(servers={"a": _sc("a")})
    t1 = FakeTarget(validation_results=[
        ValidationResult(name="check1", passed=True, message="ok"),
    ])
    v = Validator(_config(), source, {"t1": t1})
    report = v.run()
    assert report.passed is True
    assert len(report.results) == 1


def test_validator_failure():
    source = FakeSource(servers={"a": _sc("a")})
    t1 = FakeTarget(validation_results=[
        ValidationResult(name="check1", passed=False, message="bad", severity="error"),
    ])
    v = Validator(_config(), source, {"t1": t1})
    report = v.run()
    assert report.passed is False


def test_validator_target_filter():
    source = FakeSource(servers={"a": _sc("a")})
    t1 = FakeTarget(validation_results=[
        ValidationResult(name="t1-check", passed=True, message="ok"),
    ])
    t2 = FakeTarget(validation_results=[
        ValidationResult(name="t2-check", passed=False, message="bad", severity="error"),
    ])
    cfg = _config(target_names=["t1", "t2"])
    v = Validator(cfg, source, {"t1": t1, "t2": t2})

    report = v.run(target_filter="t1")
    assert report.passed is True
    assert len(report.results) == 1


def test_validator_unknown_target():
    source = FakeSource()
    v = Validator(_config(), source, {"t1": FakeTarget()})
    report = v.run(target_filter="nope")
    assert report.passed is False


def test_validator_exception_captured():
    source = FakeSource(servers={"a": _sc("a")})
    t1 = FakeTarget(raise_on_validate=True)
    v = Validator(_config(), source, {"t1": t1})
    report = v.run()
    assert report.passed is False
    assert any("boom" in r.message for r in report.results)
