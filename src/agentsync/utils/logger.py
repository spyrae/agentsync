"""Rich-based logging utilities for agentsync."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.rule import Rule


class SyncLogger:
    """Logger with rich console output and optional file flushing."""

    def __init__(self, dry_run: bool = False, quiet: bool = False) -> None:
        self.dry_run = dry_run
        self.quiet = quiet
        self._console = Console(quiet=quiet)
        self._buffer: list[str] = []

    def _record(self, msg: str, level: str = "INFO") -> None:
        prefix = "[DRY-RUN] " if self.dry_run else ""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._buffer.append(f"[{timestamp}] [{level}] {prefix}{msg}")

    def info(self, msg: str) -> None:
        self._record(msg, "INFO")
        self._console.print(f"  [green]INFO[/green]  {msg}")

    def warn(self, msg: str) -> None:
        self._record(msg, "WARN")
        self._console.print(f"  [yellow]WARN[/yellow]  {msg}")

    def error(self, msg: str) -> None:
        self._record(msg, "ERROR")
        self._console.print(f"  [red]ERROR[/red] {msg}")

    def section(self, title: str) -> None:
        self._record(f"=== {title} ===")
        self._console.print(Rule(title))

    def flush_to_file(self, log_dir: Path) -> None:
        """Write buffered messages to a dated log file."""
        if not self._buffer:
            return
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"sync-{datetime.now().strftime('%Y-%m-%d')}.log"
        with open(log_file, "a") as f:
            f.write("\n".join(self._buffer) + "\n")


class SilentLogger(SyncLogger):
    """Suppresses console output; buffer is still preserved for flush_to_file."""

    def __init__(self, dry_run: bool = False) -> None:
        super().__init__(dry_run=dry_run, quiet=True)
