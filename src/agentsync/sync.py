"""Core sync orchestrator — loads source, deduplicates, generates targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agentsync.adapters.base import ServerConfig, WriteResult
from agentsync.utils.dedup import dedup_servers
from agentsync.utils.markdown import filter_sections

if TYPE_CHECKING:
    from agentsync.adapters.base import SourceAdapter, TargetAdapter
    from agentsync.config import AgentSyncConfig


@dataclass
class TargetSyncResult:
    """Outcome of syncing a single target."""

    target_name: str
    success: bool
    writes: list[WriteResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    """Aggregate outcome of a full sync run."""

    success: bool
    dry_run: bool
    target_results: dict[str, TargetSyncResult] = field(default_factory=dict)


class SyncEngine:
    """Orchestrates sync from a single source to multiple targets."""

    def __init__(
        self,
        config: AgentSyncConfig,
        source: SourceAdapter,
        targets: dict[str, TargetAdapter],
    ) -> None:
        self._config = config
        self._source = source
        self._targets = targets

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        dry_run: bool = False,
        mcp_only: bool = False,
        rules_only: bool = False,
        target_filter: str | None = None,
    ) -> SyncResult:
        """Execute the sync pipeline.

        Returns a :class:`SyncResult` summarising what happened.
        """
        from agentsync.utils.logger import SyncLogger

        log = SyncLogger(dry_run=dry_run)
        result = SyncResult(success=True, dry_run=dry_run)

        # Determine which targets to process
        target_names = list(self._targets)
        if target_filter:
            if target_filter not in self._targets:
                log.error(f"Unknown target '{target_filter}'")
                result.success = False
                return result
            target_names = [target_filter]

        # --- MCP servers ---
        servers: dict[str, ServerConfig] = {}
        if not rules_only:
            log.section("Loading MCP servers")
            servers = self._source.load_servers()
            servers = dedup_servers(servers, log)
            log.info(f"Total: {len(servers)} unique servers after dedup")

        # --- Rules (sections) ---
        all_sections = []
        if not mcp_only:
            log.section("Loading rules")
            all_sections = self._source.load_rules()
            log.info(f"Loaded {len(all_sections)} sections from source")

        # --- Per-target processing ---
        for name in target_names:
            target = self._targets[name]
            tr = TargetSyncResult(target_name=name, success=True)

            log.section(f"Target: {name}")

            try:
                # MCP
                if not rules_only and servers:
                    filtered_servers = self._filter_servers(servers, name)
                    log.info(
                        f"{len(filtered_servers)}/{len(servers)} servers "
                        f"after filtering for {name}"
                    )
                    target.generate_mcp(filtered_servers)

                # Rules
                if not mcp_only and all_sections:
                    exclude_set = set(self._config.rules.exclude_sections)
                    filtered = filter_sections(all_sections, exclude_set)
                    log.info(
                        f"{len(filtered)}/{len(all_sections)} sections "
                        f"after filtering for {name}"
                    )
                    target.generate_rules(filtered)

                # Write
                writes = target.write(dry_run=dry_run)
                tr.writes = writes

            except Exception as exc:  # noqa: BLE001
                tr.success = False
                tr.errors.append(str(exc))
                log.error(f"{name}: {exc}")

            result.target_results[name] = tr
            if not tr.success:
                result.success = False

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _filter_servers(
        self,
        servers: dict[str, ServerConfig],
        target_name: str,
    ) -> dict[str, ServerConfig]:
        """Apply per-target exclude_servers and protocol filtering."""
        target_cfg = self._config.targets.get(target_name)
        if target_cfg is None:
            return servers

        exclude = {s.lower() for s in target_cfg.exclude_servers}
        protocols = {p.lower() for p in target_cfg.protocols}

        filtered: dict[str, ServerConfig] = {}
        for key, sc in servers.items():
            if key.lower() in exclude:
                continue
            if protocols:
                matches = (
                    ("stdio" in protocols and sc.is_stdio)
                    or ("http" in protocols and sc.is_http)
                )
                if not matches:
                    continue
            filtered[key] = sc

        return filtered
