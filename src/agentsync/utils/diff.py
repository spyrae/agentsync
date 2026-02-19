"""Server diff display utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from agentsync.adapters.base import ServerConfig

if TYPE_CHECKING:
    from agentsync.utils.logger import SyncLogger


def show_server_diff(
    target_name: str,
    existing_path: Path,
    new_servers: dict[str, ServerConfig],
    log: SyncLogger,
) -> None:
    """Log which servers are added/removed compared to an existing JSON file."""
    new_names = set(new_servers)

    if not existing_path.exists():
        log.info(
            f"{target_name}: file doesn't exist yet, "
            f"will create with {len(new_names)} servers"
        )
        return

    try:
        data = json.loads(existing_path.read_text())
        existing_names: set[str] = set(data.get("mcpServers", {}))
    except (json.JSONDecodeError, KeyError):
        existing_names = set()

    added = new_names - existing_names
    removed = existing_names - new_names

    if added:
        log.info(f"{target_name}: +{len(added)} servers ({', '.join(sorted(added))})")
    if removed:
        log.info(f"{target_name}: -{len(removed)} servers ({', '.join(sorted(removed))})")
    if not added and not removed:
        log.info(f"{target_name}: same {len(new_names)} servers")
