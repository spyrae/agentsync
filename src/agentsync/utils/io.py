"""File writing utilities that return WriteResult."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentsync.adapters.base import WriteResult
from agentsync.utils.backup import backup_file

if TYPE_CHECKING:
    from agentsync.utils.logger import SyncLogger


def write_json(
    path: Path,
    data: Any,
    log: SyncLogger,
    backup_dir: Path | None = None,
    dry_run: bool = False,
) -> WriteResult:
    """Serialize *data* as JSON and write to *path*.

    Returns a :class:`WriteResult` describing the outcome.
    """
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    # Validate round-trip
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        msg = f"JSON validation failed for {path}: {e}"
        log.error(msg)
        return WriteResult(path=str(path), written=False, message=msg)

    return _write(path, content, log, backup_dir=backup_dir, dry_run=dry_run)


def write_text(
    path: Path,
    content: str,
    log: SyncLogger,
    backup_dir: Path | None = None,
    dry_run: bool = False,
) -> WriteResult:
    """Write plain text to *path*.

    Returns a :class:`WriteResult` describing the outcome.
    """
    return _write(path, content, log, backup_dir=backup_dir, dry_run=dry_run)


# ------------------------------------------------------------------
# Internal helper
# ------------------------------------------------------------------

def _write(
    path: Path,
    content: str,
    log: SyncLogger,
    *,
    backup_dir: Path | None,
    dry_run: bool,
) -> WriteResult:
    nbytes = len(content.encode())

    if dry_run:
        if path.exists():
            existing = path.read_text()
            if existing == content:
                msg = f"{path}: no changes"
            else:
                msg = f"{path}: WOULD UPDATE ({nbytes} bytes)"
        else:
            msg = f"{path}: WOULD CREATE ({nbytes} bytes)"
        log.info(msg)
        return WriteResult(path=str(path), written=False, bytes_written=0, message=msg)

    if backup_dir is not None:
        backup_file(path, backup_dir, log)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    msg = f"Written: {path} ({nbytes} bytes)"
    log.info(msg)
    return WriteResult(path=str(path), written=True, bytes_written=nbytes, message=msg)
