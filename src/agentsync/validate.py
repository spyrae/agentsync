"""Validation orchestrator — checks all generated configs against source."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agentsync.adapters.base import ServerConfig, ValidationResult

if TYPE_CHECKING:
    from agentsync.adapters.base import SourceAdapter, TargetAdapter
    from agentsync.config import AgentSyncConfig


# ===================================================================
# Standalone check functions (reusable by adapters)
# ===================================================================


def check_server_consistency(
    expected: dict[str, ServerConfig],
    actual_names: set[str],
    target_name: str,
    exclude: set[str],
    stdio_only: bool = False,
) -> ValidationResult:
    """Check that *actual_names* contains every expected server.

    When *stdio_only* is ``True`` only stdio servers from *expected* are
    considered.
    """
    expected_names: set[str] = set()
    for k, sc in expected.items():
        if k.lower() in {e.lower() for e in exclude}:
            continue
        if stdio_only and not sc.is_stdio:
            continue
        expected_names.add(k)

    missing = expected_names - actual_names
    extra = actual_names - expected_names

    parts: list[str] = []
    if missing:
        parts.append(f"missing {len(missing)}: {', '.join(sorted(missing))}")
    if extra:
        parts.append(f"extra {len(extra)}: {', '.join(sorted(extra))}")

    if missing:
        return ValidationResult(
            name=f"{target_name} server consistency",
            passed=False,
            message="; ".join(parts),
            severity="error",
        )

    msg = f"{len(actual_names)}/{len(expected_names)} expected servers present"
    if extra:
        msg += f" ({'; '.join(parts)})"
    return ValidationResult(
        name=f"{target_name} server consistency",
        passed=True,
        message=msg,
        severity="info",
    )


def check_no_excluded_sections(
    content: str,
    exclude_set: set[str],
    label: str,
) -> ValidationResult:
    """Verify *content* doesn't contain headers from *exclude_set*."""
    leaked: list[str] = []
    for section_name in exclude_set:
        if f"## {section_name}" in content or f"### {section_name}" in content:
            leaked.append(section_name)

    if leaked:
        return ValidationResult(
            name=f"{label} excluded sections",
            passed=False,
            message=f"contains {len(leaked)} excluded sections: {', '.join(leaked[:5])}",
            severity="error",
        )

    return ValidationResult(
        name=f"{label} excluded sections",
        passed=True,
        message="no excluded sections leaked",
    )


def check_case_insensitive_duplicates(
    server_names: set[str] | list[str],
    label: str,
) -> ValidationResult:
    """Check for case-insensitive duplicate server names."""
    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str]] = []

    for key in server_names:
        lower = key.lower()
        if lower in seen:
            duplicates.append((seen[lower], key))
        else:
            seen[lower] = key

    if duplicates:
        pairs = ", ".join(f"'{a}' vs '{b}'" for a, b in duplicates)
        return ValidationResult(
            name=f"{label} case-insensitive duplicates",
            passed=False,
            message=f"duplicates found: {pairs}",
            severity="error",
        )

    return ValidationResult(
        name=f"{label} case-insensitive duplicates",
        passed=True,
        message="no case-insensitive duplicates",
    )


# ===================================================================
# ValidationReport + Validator
# ===================================================================


@dataclass
class ValidationReport:
    """Aggregate result of a validation run."""

    passed: bool
    results: list[ValidationResult] = field(default_factory=list)


class Validator:
    """Orchestrates validation of all target configs against source."""

    def __init__(
        self,
        config: AgentSyncConfig,
        source: SourceAdapter,
        targets: dict[str, TargetAdapter],
    ) -> None:
        self._config = config
        self._source = source
        self._targets = targets

    def run(
        self,
        *,
        verbose: bool = False,
        target_filter: str | None = None,
    ) -> ValidationReport:
        """Run all validation checks and return a :class:`ValidationReport`."""
        report = ValidationReport(passed=True)

        # Determine targets
        target_names = list(self._targets)
        if target_filter:
            if target_filter not in self._targets:
                report.passed = False
                report.results.append(
                    ValidationResult(
                        name="target filter",
                        passed=False,
                        message=f"Unknown target '{target_filter}'",
                    )
                )
                return report
            target_names = [target_filter]

        # Per-target adapter validation
        for name in target_names:
            target = self._targets[name]
            try:
                vr_list = target.validate()
                for vr in vr_list:
                    report.results.append(vr)
                    if not vr.passed and vr.severity == "error":
                        report.passed = False
            except Exception as exc:  # noqa: BLE001
                report.passed = False
                report.results.append(
                    ValidationResult(
                        name=f"{name} validation",
                        passed=False,
                        message=str(exc),
                    )
                )

        return report
