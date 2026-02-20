"""Rich output helpers for CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from agentsync.adapters.base import SourceAdapter, TargetAdapter
    from agentsync.config import AgentSyncConfig
    from agentsync.sync import SyncResult
    from agentsync.validate import ValidationReport


def print_sync_summary(result: SyncResult, console: Console | None = None) -> None:
    """Print a coloured summary of sync results."""
    con = console or Console()

    total_files = 0
    total_errors = 0

    for tr in result.target_results.values():
        total_files += sum(1 for w in tr.writes if w.written)
        total_errors += len(tr.errors)

    n_targets = len(result.target_results)
    header = f"Sync complete: {n_targets} target{'s' if n_targets != 1 else ''}"
    header += f", {total_files} file{'s' if total_files != 1 else ''} written"
    if total_errors:
        header += f", [red]{total_errors} error{'s' if total_errors != 1 else ''}[/red]"
    else:
        header += ", 0 errors"

    con.print()
    con.print(header)

    for name, tr in result.target_results.items():
        n_written = sum(1 for w in tr.writes if w.written)
        if tr.success:
            mark = "[green]\u2713[/green]"
            detail = f"{n_written} file{'s' if n_written != 1 else ''}"
        else:
            mark = "[red]\u2717[/red]"
            detail = "; ".join(tr.errors) if tr.errors else "failed"

        con.print(f"  {name:<16} {mark}  {detail}")

    if result.dry_run:
        con.print()
        con.print("[yellow]DRY RUN \u2014 no files were written[/yellow]")


def print_validation_report(
    report: ValidationReport,
    verbose: bool = False,
    console: Console | None = None,
) -> None:
    """Print a coloured validation report."""
    con = console or Console()

    passed = sum(1 for r in report.results if r.passed)
    failed = sum(1 for r in report.results if not r.passed)

    con.print()

    for r in report.results:
        if r.passed and not verbose:
            continue
        mark = "[green]\u2713[/green]" if r.passed else "[red]\u2717[/red]"
        con.print(f"  {mark} {r.name}: {r.message}")

    con.print()
    parts = []
    if passed:
        parts.append(f"[green]{passed} passed[/green]")
    if failed:
        parts.append(f"[red]{failed} failed[/red]")
    con.print(f"Validation: {', '.join(parts)}")


def print_status(
    config: AgentSyncConfig,
    source: SourceAdapter,
    targets: dict[str, TargetAdapter],
    console: Console | None = None,
) -> None:
    """Print current sync status: source info and per-target state."""
    from agentsync.config import resolve_path

    con = console or Console()

    # --- Source ---
    con.print()
    con.print(f"[bold]Source:[/bold] {config.source.type}")

    global_path = resolve_path(config.source.global_config, config.config_dir)
    _print_path_status(con, "Global config", global_path)

    project_mcp = resolve_path(config.source.project_mcp, config.config_dir)
    server_count = None
    if project_mcp.is_file():
        try:
            servers = source.load_servers()
            server_count = len(servers)
        except Exception:  # noqa: BLE001
            server_count = None
    _print_path_status(con, "Project MCP", project_mcp, extra_count=server_count)

    rules_path = resolve_path(config.source.rules_file, config.config_dir)
    _print_path_status(con, "Rules", rules_path)

    # --- Targets ---
    con.print()
    con.print("[bold]Targets:[/bold]")

    table = Table(show_header=True, show_edge=False, pad_edge=False, box=None)
    table.add_column("Name", style="cyan", min_width=14)
    table.add_column("Status", min_width=10)
    table.add_column("Details")

    for name, target in targets.items():
        try:
            results = target.validate()
            all_pass = all(r.passed for r in results)
            if not results:
                mark = "[yellow]\u26a0[/yellow]"
                detail = "no validation checks"
            elif all_pass:
                mark = "[green]\u2713[/green]"
                detail = f"{len(results)} check{'s' if len(results) != 1 else ''} passed"
            else:
                n_fail = sum(1 for r in results if not r.passed)
                mark = "[red]\u2717[/red]"
                detail = f"{n_fail} check{'s' if n_fail != 1 else ''} failed"
        except Exception as exc:  # noqa: BLE001
            mark = "[red]\u2717[/red]"
            detail = str(exc)

        table.add_row(name, mark, detail)

    con.print(table)


def _print_path_status(
    con: Console,
    label: str,
    path: Path,
    *,
    extra_count: int | None = None,
) -> None:
    """Print a source path with exists/missing indicator."""
    if path.is_file():
        suffix = f" ({extra_count} servers)" if extra_count is not None else ""
        con.print(f"  {label + ':':<18} {path} [green](exists{suffix})[/green]")
    else:
        con.print(f"  {label + ':':<18} {path} [yellow](missing)[/yellow]")
