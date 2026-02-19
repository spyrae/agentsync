"""Config file loading and validation for agentsync.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


CONFIG_FILENAME = "agentsync.yaml"
SUPPORTED_VERSIONS = {1}
KNOWN_SOURCE_TYPES = {"claude"}
KNOWN_TARGET_TYPES = {"cursor", "codex", "antigravity"}


# === Config Dataclasses ===


@dataclass
class SourceConfig:
    """Source of truth configuration."""

    type: str = "claude"
    global_config: str = "~/.claude.json"
    project_mcp: str = ".mcp.json"
    rules_file: str = "CLAUDE.md"


@dataclass
class TargetConfig:
    """Single target agent configuration."""

    type: str
    mcp_path: str = ""
    config_path: str = ""  # For TOML-based configs (Codex)
    rules_path: str = ""
    rules_format: str = "md"  # md or mdc
    exclude_servers: list[str] = field(default_factory=list)
    protocols: list[str] = field(default_factory=list)  # e.g. ["stdio"]


@dataclass
class RulesConfig:
    """Rules filtering configuration."""

    exclude_sections: list[str] = field(default_factory=list)


@dataclass
class SyncOptions:
    """Sync behavior options."""

    backup: bool = True
    backup_dir: str = ".agentsync/backups"
    log_dir: str = ".agentsync/logs"


@dataclass
class AgentSyncConfig:
    """Top-level agentsync configuration."""

    version: int = 1
    source: SourceConfig = field(default_factory=SourceConfig)
    targets: dict[str, TargetConfig] = field(default_factory=dict)
    rules: RulesConfig = field(default_factory=RulesConfig)
    sync: SyncOptions = field(default_factory=SyncOptions)

    # Resolved at load time (not from YAML)
    config_dir: Path = field(default_factory=lambda: Path.cwd())


# === Errors ===


class ConfigError(Exception):
    """Raised when config file is invalid or missing."""


# === Path Resolution ===


def resolve_path(path_str: str, base_dir: Path) -> Path:
    """Resolve a path string: expand ~ and make relative paths absolute."""
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = base_dir / p
    return p


# === Config Discovery ===


def find_config(start_dir: Path | None = None) -> Path | None:
    """Find agentsync.yaml by walking up from start_dir (or cwd)."""
    current = (start_dir or Path.cwd()).resolve()

    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.is_file():
            return candidate

        parent = current.parent
        if parent == current:
            return None  # Reached filesystem root
        current = parent


# === Parsing ===


def _parse_source(raw: dict[str, Any]) -> SourceConfig:
    source_type = raw.get("type", "claude")
    if source_type not in KNOWN_SOURCE_TYPES:
        raise ConfigError(
            f"Unknown source type '{source_type}'. Supported: {', '.join(sorted(KNOWN_SOURCE_TYPES))}"
        )
    return SourceConfig(
        type=source_type,
        global_config=raw.get("global_config", SourceConfig.global_config),
        project_mcp=raw.get("project_mcp", SourceConfig.project_mcp),
        rules_file=raw.get("rules_file", SourceConfig.rules_file),
    )


def _parse_target(name: str, raw: dict[str, Any]) -> TargetConfig:
    target_type = raw.get("type")
    if not target_type:
        raise ConfigError(f"Target '{name}' is missing required field 'type'")
    if target_type not in KNOWN_TARGET_TYPES:
        raise ConfigError(
            f"Target '{name}': unknown type '{target_type}'. "
            f"Supported: {', '.join(sorted(KNOWN_TARGET_TYPES))}"
        )

    rules_format = raw.get("rules_format", "md")
    if rules_format not in ("md", "mdc"):
        raise ConfigError(
            f"Target '{name}': rules_format must be 'md' or 'mdc', got '{rules_format}'"
        )

    exclude_servers = raw.get("exclude_servers", [])
    if not isinstance(exclude_servers, list) or not all(isinstance(s, str) for s in exclude_servers):
        raise ConfigError(f"Target '{name}': exclude_servers must be a list of strings")

    protocols = raw.get("protocols", [])
    if not isinstance(protocols, list) or not all(isinstance(p, str) for p in protocols):
        raise ConfigError(f"Target '{name}': protocols must be a list of strings")

    return TargetConfig(
        type=target_type,
        mcp_path=raw.get("mcp_path", ""),
        config_path=raw.get("config_path", ""),
        rules_path=raw.get("rules_path", ""),
        rules_format=rules_format,
        exclude_servers=exclude_servers,
        protocols=protocols,
    )


def _parse_targets(raw: dict[str, Any]) -> dict[str, TargetConfig]:
    targets = {}
    for name, target_raw in raw.items():
        if not isinstance(target_raw, dict):
            raise ConfigError(f"Target '{name}' must be a mapping, got {type(target_raw).__name__}")
        targets[name] = _parse_target(name, target_raw)
    return targets


def _parse_rules(raw: dict[str, Any]) -> RulesConfig:
    exclude = raw.get("exclude_sections", [])
    if not isinstance(exclude, list):
        raise ConfigError("rules.exclude_sections must be a list")
    return RulesConfig(exclude_sections=exclude)


def _parse_sync_options(raw: dict[str, Any]) -> SyncOptions:
    backup = raw.get("backup", True)
    if not isinstance(backup, bool):
        raise ConfigError(f"sync.backup must be a boolean, got {type(backup).__name__}")
    return SyncOptions(
        backup=backup,
        backup_dir=raw.get("backup_dir", SyncOptions.backup_dir),
        log_dir=raw.get("log_dir", SyncOptions.log_dir),
    )


# === Loading ===


def load_config(config_path: Path) -> AgentSyncConfig:
    """Load and validate agentsync.yaml from a specific path."""
    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {config_path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"Config file must be a YAML mapping, got {type(raw).__name__}")

    # Version check
    version = raw.get("version")
    if version is None:
        raise ConfigError("Missing required field 'version'")
    if not isinstance(version, int):
        raise ConfigError(f"'version' must be an integer, got {type(version).__name__}")
    if version not in SUPPORTED_VERSIONS:
        raise ConfigError(
            f"Unsupported config version {version}. Supported: {sorted(SUPPORTED_VERSIONS)}"
        )

    # Parse sections
    config_dir = config_path.parent.resolve()

    source = _parse_source(raw.get("source", {}))
    targets = _parse_targets(raw.get("targets", {}))
    rules = _parse_rules(raw.get("rules", {}))
    sync_opts = _parse_sync_options(raw.get("sync", {}))

    if not targets:
        raise ConfigError("At least one target must be defined in 'targets'")

    return AgentSyncConfig(
        version=version,
        source=source,
        targets=targets,
        rules=rules,
        sync=sync_opts,
        config_dir=config_dir,
    )


def load(config_path: str | Path | None = None) -> AgentSyncConfig:
    """Load config from explicit path or discover agentsync.yaml.

    Args:
        config_path: Explicit path to config file, or None to auto-discover.

    Returns:
        Parsed AgentSyncConfig.

    Raises:
        ConfigError: If config is not found or invalid.
    """
    if config_path is not None:
        return load_config(Path(config_path).resolve())

    found = find_config()
    if not found:
        raise ConfigError(
            f"No {CONFIG_FILENAME} found in current directory or any parent. "
            f"Run 'agentsync init' to create one."
        )
    return load_config(found)


# === Default Config Generation ===


DEFAULT_CONFIG = """\
# agentsync.yaml — Sync MCP server configs and rules across AI coding agents
# See: https://github.com/spyrae/agentsync

version: 1

# Source of truth — where to read MCP servers and rules from
source:
  type: claude                    # Currently only "claude" is supported
  global_config: ~/.claude.json   # Claude Code global config
  project_mcp: .mcp.json         # Project-level MCP servers
  rules_file: CLAUDE.md           # Project rules (Markdown)

# Target agents — where to write synced configs
targets:
  cursor:
    type: cursor
    mcp_path: ~/.cursor/mcp.json
    rules_path: .cursor/rules/project.mdc
    rules_format: mdc              # MDC = Markdown with YAML frontmatter
    exclude_servers: []

  codex:
    type: codex
    config_path: ~/.codex/config.toml
    rules_path: AGENTS.md
    rules_format: md
    exclude_servers:
      - codex                      # Codex can't call itself

  antigravity:
    type: antigravity
    mcp_path: ~/.gemini/antigravity/mcp_config.json
    protocols:
      - stdio                      # Only stdio servers (no HTTP)
    exclude_servers: []

# Rules filtering — sections to exclude from generated rules
rules:
  exclude_sections:
    # Add section headers (## or ###) that are agent-specific
    # and should NOT appear in generated rules for other agents
    - "MCP Servers"
    - "Context Management & Agents"

# Sync options
sync:
  backup: true                     # Create backups before writing
  backup_dir: .agentsync/backups   # Where to store backups
  log_dir: .agentsync/logs         # Where to store sync logs
"""


def generate_default_config(target_dir: Path, force: bool = False) -> Path:
    """Write default agentsync.yaml to target_dir.

    Returns:
        Path to the created config file.

    Raises:
        ConfigError: If file already exists and force=False.
    """
    target = target_dir / CONFIG_FILENAME
    if target.exists() and not force:
        raise ConfigError(f"{CONFIG_FILENAME} already exists. Use --force to overwrite.")

    target.write_text(DEFAULT_CONFIG)
    return target
