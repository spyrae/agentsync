"""Claude Code source adapter — reads MCP servers and rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentsync.adapters.base import Section, ServerConfig, SourceAdapter
from agentsync.config import AgentSyncConfig, resolve_path
from agentsync.utils.logger import SilentLogger, SyncLogger
from agentsync.utils.markdown import parse_markdown_sections


class ClaudeSourceAdapter(SourceAdapter):
    """Reads MCP servers and rules from Claude Code configuration files.

    MCP servers are merged from three tiers (lowest → highest priority):
    1. ``~/.claude.json`` top-level ``mcpServers``  (global)
    2. ``~/.claude.json`` → ``projects[config_dir].mcpServers``  (project-specific)
    3. ``.mcp.json`` → ``mcpServers``  (local project override)

    Rules are parsed from ``CLAUDE.md`` via :func:`parse_markdown_sections`.
    """

    def __init__(
        self,
        config: AgentSyncConfig,
        logger: SyncLogger | None = None,
    ) -> None:
        self._config = config
        self._log = logger or SilentLogger()

    # ------------------------------------------------------------------
    # SourceAdapter interface
    # ------------------------------------------------------------------

    def load_servers(self) -> dict[str, ServerConfig]:
        """Load and merge MCP servers from all three tiers."""
        merged: dict[str, ServerConfig] = {}

        # Tier 1 & 2: ~/.claude.json (global + project-specific)
        global_path = resolve_path(self._config.source.global_config, self._config.config_dir)
        global_data = self._read_json(global_path)

        if global_data is not None:
            # Tier 1: top-level mcpServers
            top_level = global_data.get("mcpServers", {})
            if isinstance(top_level, dict):
                merged.update(self._extract_servers(top_level))
                self._log.info(f"Global config: {len(top_level)} servers from {global_path}")

            # Tier 2: projects[config_dir].mcpServers
            projects = global_data.get("projects", {})
            if isinstance(projects, dict):
                project_key = str(self._config.config_dir)
                project_block = projects.get(project_key, {})
                if isinstance(project_block, dict):
                    project_servers = project_block.get("mcpServers", {})
                    if isinstance(project_servers, dict) and project_servers:
                        extracted = self._extract_servers(project_servers)
                        merged.update(extracted)
                        self._log.info(
                            f"Project config: {len(project_servers)} servers for {project_key}"
                        )

        # Tier 3: .mcp.json (highest priority)
        mcp_path = resolve_path(self._config.source.project_mcp, self._config.config_dir)
        mcp_data = self._read_json(mcp_path)

        if mcp_data is not None:
            local_servers = mcp_data.get("mcpServers", {})
            if isinstance(local_servers, dict):
                merged.update(self._extract_servers(local_servers))
                self._log.info(f"Local .mcp.json: {len(local_servers)} servers from {mcp_path}")

        return merged

    def load_rules(self) -> list[Section]:
        """Load and parse rules from CLAUDE.md."""
        rules_path = resolve_path(self._config.source.rules_file, self._config.config_dir)

        if not rules_path.is_file():
            self._log.warn(f"Rules file not found: {rules_path}")
            return []

        try:
            content = rules_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self._log.warn(f"Cannot read {rules_path}: {exc}")
            return []

        if not content.strip():
            self._log.warn(f"Rules file is empty: {rules_path}")
            return []

        sections = parse_markdown_sections(content)
        self._log.info(f"Loaded {len(sections)} sections from {rules_path}")
        return sections

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        """Safely read a JSON file. Returns None on missing file or invalid JSON."""
        if not path.is_file():
            self._log.warn(f"File not found: {path}")
            return None

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            self._log.warn(f"Cannot read {path}: {exc}")
            return None

        if not isinstance(raw, dict):
            self._log.warn(f"Expected JSON object in {path}, got {type(raw).__name__}")
            return None

        return raw

    def _extract_servers(self, raw: dict[str, Any]) -> dict[str, ServerConfig]:
        """Convert a raw ``mcpServers`` dict into ``{name: ServerConfig}``."""
        result: dict[str, ServerConfig] = {}
        for name, cfg in raw.items():
            if isinstance(cfg, dict):
                result[name] = ServerConfig(name=name, config=cfg)
        return result
