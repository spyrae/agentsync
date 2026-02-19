"""Codex target adapter — TOML MCP config + Markdown rules."""

from __future__ import annotations

import re
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
from agentsync.utils.io import write_text
from agentsync.utils.logger import SilentLogger, SyncLogger
from agentsync.validate import check_server_consistency

MARKER_START = "# === AGENTSYNC START ==="
MARKER_END = "# === AGENTSYNC END ==="


class CodexTargetAdapter(TargetAdapter):
    """Writes MCP servers as TOML (with markers) and rules as Markdown for Codex."""

    def __init__(
        self,
        target_config: TargetConfig,
        config: AgentSyncConfig,
        logger: SyncLogger | None = None,
    ) -> None:
        self._tc = target_config
        self._config = config
        self._log = logger or SilentLogger()
        self._mcp_text: str | None = None
        self._rules_text: str | None = None

    # ------------------------------------------------------------------
    # TargetAdapter interface
    # ------------------------------------------------------------------

    def generate_mcp(self, servers: dict[str, ServerConfig]) -> str:
        lines: list[str] = []
        for name, sc in servers.items():
            lines.append(_server_to_toml(name, sc.config))
        inner = "\n".join(lines)
        self._mcp_text = f"{MARKER_START}\n{inner}\n{MARKER_END}\n"
        return self._mcp_text

    def generate_rules(self, sections: list[Section]) -> str:
        text = "\n\n".join(s.content for s in sections)
        self._rules_text = text + "\n" if text else ""
        return self._rules_text

    def write(self, dry_run: bool = False) -> list[WriteResult]:
        results: list[WriteResult] = []
        backup_dir = self._backup_dir()

        if self._mcp_text is not None and self._tc.config_path:
            path = resolve_path(self._tc.config_path, self._config.config_dir)
            content = self._merge_toml(path, self._mcp_text)
            results.append(write_text(path, content, self._log, backup_dir, dry_run))

        if self._rules_text is not None and self._tc.rules_path:
            path = resolve_path(self._tc.rules_path, self._config.config_dir)
            results.append(write_text(path, self._rules_text, self._log, backup_dir, dry_run))

        return results

    def validate(self) -> list[ValidationResult]:
        results: list[ValidationResult] = []

        config_path = (
            resolve_path(self._tc.config_path, self._config.config_dir)
            if self._tc.config_path else None
        )
        if config_path and config_path.is_file():
            content = config_path.read_text(encoding="utf-8")
            if MARKER_START in content and MARKER_END in content:
                actual = _extract_server_names(content)
                expected = self._load_expected_servers()
                exclude = set(self._tc.exclude_servers)
                results.append(check_server_consistency(expected, actual, "codex", exclude))
            else:
                results.append(ValidationResult(
                    name="codex markers",
                    passed=True,
                    message="No agentsync markers found in config.toml",
                    severity="warning",
                ))
        else:
            results.append(ValidationResult(
                name="codex config file",
                passed=True,
                message="Config file does not exist yet",
                severity="info",
            ))

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _merge_toml(self, path: Path, managed_block: str) -> str:
        """Merge managed block into existing TOML, or create a new file."""
        if not path.is_file():
            return managed_block

        existing = path.read_text(encoding="utf-8")
        if MARKER_START in existing and MARKER_END in existing:
            # Replace content between markers (inclusive)
            pattern = re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\n?"
            return re.sub(pattern, managed_block, existing, flags=re.DOTALL)

        # No markers — append
        sep = "" if existing.endswith("\n") else "\n"
        return existing + sep + "\n" + managed_block

    def _backup_dir(self) -> Path | None:
        if not self._config.sync.backup:
            return None
        return resolve_path(self._config.sync.backup_dir, self._config.config_dir)

    def _load_expected_servers(self) -> dict[str, ServerConfig]:
        from agentsync.adapters.claude import ClaudeSourceAdapter

        source = ClaudeSourceAdapter(self._config)
        return source.load_servers()


# ===================================================================
# TOML helpers (no external dependencies — Python 3.9+)
# ===================================================================


def _toml_value(val: Any) -> str:
    """Serialize a single Python value to TOML literal."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return str(val)
    if isinstance(val, str):
        # Escape backslashes and double quotes
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(val, list):
        items = ", ".join(_toml_value(v) for v in val)
        return f"[{items}]"
    if isinstance(val, dict):
        # Inline table
        pairs = ", ".join(f"{k} = {_toml_value(v)}" for k, v in val.items())
        return "{" + pairs + "}"
    return repr(val)


def _server_to_toml(name: str, config: dict[str, Any]) -> str:
    """Render a single server config as a TOML table."""
    # Codex uses underscores in table names
    safe_name = name.replace("-", "_")
    lines = [f"[mcp_servers.{safe_name}]"]
    for key, val in config.items():
        lines.append(f"{key} = {_toml_value(val)}")
    return "\n".join(lines) + "\n"


def _extract_server_names(content: str) -> set[str]:
    """Extract server names from TOML [mcp_servers.xxx] headers."""
    return set(re.findall(r"\[mcp_servers\.(.+?)\]", content))
