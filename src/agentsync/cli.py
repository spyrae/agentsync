"""CLI entry point for agentsync."""

from __future__ import annotations

import click

from agentsync import __version__


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
    click.echo("agentsync sync — not yet implemented")
    raise SystemExit(0)


@main.command()
@click.option("--verbose", "-v", is_flag=True, help="Show details for passed checks too.")
@click.option("--target", "-t", help="Validate only a specific target agent.")
@click.pass_context
def validate(ctx: click.Context, verbose: bool, target: str | None) -> None:
    """Validate all generated agent configs against source of truth."""
    click.echo("agentsync validate — not yet implemented")
    raise SystemExit(0)


@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing agentsync.yaml.")
def init(force: bool) -> None:
    """Create an agentsync.yaml config file with sensible defaults."""
    click.echo("agentsync init — not yet implemented")
    raise SystemExit(0)


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current sync state and detect drift."""
    click.echo("agentsync status — not yet implemented")
    raise SystemExit(0)
