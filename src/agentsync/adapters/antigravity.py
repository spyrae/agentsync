"""Antigravity/Gemini target adapter — JSON MCP config (stdio only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentsync.adapters.base import (
    Section,
    ServerConfig,
    TargetAdapter,
    ValidationResult,
    WriteResult,
)
from agentsync.config import AgentSyncConfig, TargetConfig, resolve_path
from agentsync.utils.io import write_json
from agentsync.utils.logger import SilentLogger, SyncLogger
from agentsync.validate import check_server_consistency


class AntigravityTargetAdapter(TargetAdapter):
    """Writes MCP servers as JSON for Antigravity/Gemini. Rules are not supported."""

    def __init__(
        self,
        target_config: TargetConfig,
        config: AgentSyncConfig,
        logger: SyncLogger | None = None,
    ) -> None:
        self._tc = target_config
        self._config = config
        self._log = logger or SilentLogger()
        self._mcp_data: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # TargetAdapter interface
    # ------------------------------------------------------------------

    def generate_mcp(self, servers: dict[str, ServerConfig]) -> dict[str, Any]:
        data = {"mcpServers": {n: s.config for n, s in servers.items()}}
        self._mcp_data = data
        return data

    def generate_rules(self, sections: list[Section]) -> str:
        return ""

    def write(self, dry_run: bool = False) -> list[WriteResult]:
        results: list[WriteResult] = []
        backup_dir = self._backup_dir()

        if self._mcp_data is not None and self._tc.mcp_path:
            path = resolve_path(self._tc.mcp_path, self._config.config_dir)
            results.append(write_json(path, self._mcp_data, self._log, backup_dir, dry_run))

        # Rules are not supported — skip entirely
        return results

    def validate(self) -> list[ValidationResult]:
        results: list[ValidationResult] = []

        mcp_path = (
            resolve_path(self._tc.mcp_path, self._config.config_dir) if self._tc.mcp_path else None
        )
        if mcp_path and mcp_path.is_file():
            try:
                data = json.loads(mcp_path.read_text(encoding="utf-8"))
                actual = set(data.get("mcpServers", {}))
            except (json.JSONDecodeError, OSError):
                actual = set()

            expected = self._load_expected_servers()
            exclude = set(self._tc.exclude_servers)
            results.append(
                check_server_consistency(expected, actual, "antigravity", exclude, stdio_only=True)
            )
        else:
            results.append(
                ValidationResult(
                    name="antigravity mcp file",
                    passed=True,
                    message="MCP file does not exist yet",
                    severity="info",
                )
            )

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _backup_dir(self) -> Path | None:
        if not self._config.sync.backup:
            return None
        return resolve_path(self._config.sync.backup_dir, self._config.config_dir)

    def _load_expected_servers(self) -> dict[str, ServerConfig]:
        from agentsync.adapters.claude import ClaudeSourceAdapter

        source = ClaudeSourceAdapter(self._config)
        return source.load_servers()
