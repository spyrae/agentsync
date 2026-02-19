"""File backup utilities."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentsync.utils.logger import SyncLogger


def backup_file(path: Path, backup_dir: Path, log: SyncLogger) -> Path | None:
    """Create a timestamped backup of *path* inside *backup_dir*.

    Returns the backup path on success, or ``None`` if the source file
    does not exist.
    """
    if not path.exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{path.name}.{timestamp}.bak"
    backup_path = backup_dir / backup_name
    shutil.copy2(path, backup_path)
    log.info(f"Backup: {path} -> {backup_path}")
    return backup_path
