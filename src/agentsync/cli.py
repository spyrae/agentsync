"""CLI entry point for agentsync."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from agentsync import __version__

if TYPE_CHECKING:
    from agentsync.adapters.base import SourceAdapter, TargetAdapter
    from agentsync.config import AgentSyncConfig


# ===================================================================
# Adapter registry (stubs — real adapters registered in RB-276/277)
# ===================================================================


class AdapterError(Exception):
    """Raised when no adapter is registered for a given type."""


def create_source(config: AgentSyncConfig) -> SourceAdapter:
    """Instantiate a source adapter from *config.source.type*."""
    if config.source.type == "claude":
        from agentsync.adapters.claude import ClaudeSourceAdapter

        return ClaudeSourceAdapter(config)

    raise AdapterError(
        f"No adapter registered for source type '{config.source.type}'."
    )


def create_targets(config: AgentSyncConfig) -> dict[str, TargetAdapter]:
    """Instantiate target adapters from *config.targets*."""
    targets: dict[str, TargetAdapter] = {}
    for name, tc in config.targets.items():
        if tc.type == "cursor":
            from agentsync.adapters.cursor import CursorTargetAdapter

            targets[name] = CursorTargetAdapter(tc, config)
        elif tc.type == "codex":
            from agentsync.adapters.codex import CodexTargetAdapter

            targets[name] = CodexTargetAdapter(tc, config)
        elif tc.type == "antigravity":
            from agentsync.adapters.antigravity import AntigravityTargetAdapter

            targets[name] = AntigravityTargetAdapter(tc, config)
        else:
            raise AdapterError(
                f"No adapter registered for target type '{tc.type}'."
            )
    return targets


# ===================================================================
# CLI group
# ===================================================================


@click.group()
@click.version_option(version=__version__, prog_name="agentsync")
@click.option("--config", "-c", type=click.Path(), help="Path to agentsync.yaml config file.")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output.")
@click.pass_context
def main(ctx: click.Context, config: str | None, quiet: bool) -> None:
    """Sync MCP server configs and rules across AI coding agents."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["quiet"] = quiet


# ===================================================================
# sync
# ===================================================================


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would change without writing files.")
@click.option("--mcp-only", is_flag=True, help="Sync only MCP server configs.")
@click.option("--rules-only", is_flag=True, help="Sync only rules files.")
@click.option("--target", "-t", help="Sync only a specific target agent.")
@click.option("--no-backup", is_flag=True, help="Skip creating backups before writing.")
@click.pass_context
def sync(
    ctx: click.Context,
    dry_run: bool,
    mcp_only: bool,
    rules_only: bool,
    target: str | None,
    no_backup: bool,
) -> None:
    """Sync configs from source of truth to target agents."""
    from agentsync.config import ConfigError, load

    try:
        cfg = load(ctx.obj["config_path"])
    except ConfigError as e:
        raise SystemExit(f"Error: {e}")

    try:
        source = create_source(cfg)
        targets = create_targets(cfg)
    except AdapterError as e:
        raise SystemExit(f"Error: {e}")

    from agentsync.sync import SyncEngine

    engine = SyncEngine(cfg, source, targets)
    result = engine.run(
        dry_run=dry_run,
        mcp_only=mcp_only,
        rules_only=rules_only,
        target_filter=target,
    )
    raise SystemExit(0 if result.success else 1)


# ===================================================================
# validate
# ===================================================================


@main.command()
@click.option("--verbose", "-v", is_flag=True, help="Show details for passed checks too.")
@click.option("--target", "-t", help="Validate only a specific target agent.")
@click.pass_context
def validate(ctx: click.Context, verbose: bool, target: str | None) -> None:
    """Validate all generated agent configs against source of truth."""
    from agentsync.config import ConfigError, load

    try:
        cfg = load(ctx.obj["config_path"])
    except ConfigError as e:
        raise SystemExit(f"Error: {e}")

    try:
        source = create_source(cfg)
        targets = create_targets(cfg)
    except AdapterError as e:
        raise SystemExit(f"Error: {e}")

    from agentsync.validate import Validator

    validator = Validator(cfg, source, targets)
    report = validator.run(verbose=verbose, target_filter=target)
    raise SystemExit(0 if report.passed else 1)


# ===================================================================
# init
# ===================================================================


@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing agentsync.yaml.")
def init(force: bool) -> None:
    """Create an agentsync.yaml config file with sensible defaults."""
    from agentsync.config import ConfigError, generate_default_config

    try:
        path = generate_default_config(Path.cwd(), force=force)
        click.echo(f"Created {path}")
    except ConfigError as e:
        raise SystemExit(f"Error: {e}")


# ===================================================================
# status
# ===================================================================


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current sync state and detect drift."""
    click.echo("agentsync status — not yet implemented")
    raise SystemExit(0)
