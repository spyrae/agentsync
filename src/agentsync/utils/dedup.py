"""Case-insensitive server deduplication."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentsync.adapters.base import ServerConfig

if TYPE_CHECKING:
    from agentsync.utils.logger import SyncLogger


def dedup_servers(
    servers: dict[str, ServerConfig],
    log: SyncLogger,
) -> dict[str, ServerConfig]:
    """Deduplicate servers by case-insensitive key comparison.

    When two keys differ only by case (e.g. ``Notion`` vs ``notion``),
    the later entry wins.  All returned keys are lowercase.
    """
    seen: dict[str, tuple[str, ServerConfig]] = {}

    for key, sc in servers.items():
        lower = key.lower()
        if lower in seen:
            prev_key = seen[lower][0]
            if prev_key != key:
                log.warn(f"Dedup: '{prev_key}' replaced by '{key}' (case-insensitive merge)")
        seen[lower] = (key, sc)

    return {lower: sc for lower, (_orig, sc) in seen.items()}
