# agentsync

**Sync MCP server configs and rules across AI coding agents.**

[![CI](https://github.com/spyrae/agentsync/actions/workflows/ci.yml/badge.svg)](https://github.com/spyrae/agentsync/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentsync)](https://pypi.org/project/agentsync/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

---

## The Problem

You use multiple AI coding agents — Claude Code, Cursor, Codex, Gemini. Each stores MCP server configs in its own format (JSON, TOML) and its own location. Keeping them in sync manually is tedious and error-prone.

## The Solution

**agentsync** takes a single source of truth (your Claude Code config) and syncs it to all your agents with one command.

```
┌──────────────┐
│  Claude Code │  Source of Truth
│  .claude.json│  ─── MCP Servers
│  .mcp.json   │  ─── Rules (CLAUDE.md)
│  CLAUDE.md   │
└──────┬───────┘
       │  agentsync sync
       ├──────────────────┐─────────────────┐
       ▼                  ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│    Cursor    │  │    Codex     │  │  Antigravity │
│  mcp.json   │  │ config.toml  │  │mcp_config.json│
│ project.mdc │  │  AGENTS.md   │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Installation

```bash
pip install agentsync     # pip
pipx install agentsync    # pipx (recommended for CLI tools)
uvx agentsync             # uv (run without installing)
```

## Quick Start

```bash
agentsync init       # Create agentsync.yaml config
agentsync sync       # Sync to all agents
agentsync validate   # Verify everything is correct
```

## Features

- **MCP server sync** — JSON ↔ TOML automatic conversion
- **Rules sync** — Markdown → filtered Markdown / MDC with frontmatter
- **Case-insensitive deduplication** — handles `Notion` vs `notion` from different sources
- **Dry-run mode** — preview changes before writing
- **Backups** — automatic backups before every write
- **Validation** — structural checks, consistency, duplicate detection
- **Extensible** — adapter-based architecture for adding new agents

## Supported Agents

| Agent | MCP Format | Rules Format | Status |
|-------|-----------|-------------|--------|
| Claude Code | JSON | Markdown | Source |
| Cursor | JSON | MDC | Target |
| Codex | TOML | Markdown | Target |
| Antigravity (Gemini) | JSON | — | Target |

## Configuration

Create `agentsync.yaml` in your project root:

```yaml
version: 1

source:
  type: claude
  global_config: ~/.claude.json
  project_mcp: .mcp.json
  rules_file: CLAUDE.md

targets:
  cursor:
    type: cursor
    mcp_path: ~/.cursor/mcp.json
    rules_path: .cursor/rules/project.mdc
    exclude_servers: []

  codex:
    type: codex
    config_path: ~/.codex/config.toml
    rules_path: AGENTS.md
    exclude_servers: [codex]

  antigravity:
    type: antigravity
    mcp_path: ~/.gemini/antigravity/mcp_config.json
    protocols: [stdio]

rules:
  exclude_sections:
    - "MCP Servers"
    - "Context Management & Agents"
```

## CLI Reference

### Global Options

| Option | Description |
|--------|-------------|
| `--config, -c PATH` | Path to agentsync.yaml (default: auto-discover) |
| `--quiet, -q` | Minimal output |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

### Commands

```bash
# Sync — push source configs to targets
agentsync sync                  # Full sync (MCP + rules)
agentsync sync --dry-run        # Preview changes without writing
agentsync sync --mcp-only       # Only MCP server configs
agentsync sync --rules-only     # Only rules files
agentsync sync -t cursor        # Sync specific target only
agentsync sync --no-backup      # Skip creating backup files

# Validate — check target configs match source
agentsync validate              # Full validation
agentsync validate -v           # Verbose (show passed checks too)
agentsync validate -t codex     # Validate specific target only

# Init — create config
agentsync init                  # Create agentsync.yaml
agentsync init --force          # Overwrite existing config

# Status — show sync state
agentsync status                # Source info, target health, drift
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Runtime error (sync failed, validation failed) |
| `2` | Configuration error (missing config, bad YAML, unknown adapter) |

## How It Works

```
agentsync sync
  │
  ├─ Load config (agentsync.yaml)
  ├─ Read source (Claude Code)
  │   ├─ ~/.claude.json         → global MCP servers
  │   ├─ .mcp.json              → project MCP servers
  │   └─ CLAUDE.md              → rules sections
  │
  ├─ Deduplicate (case-insensitive)
  ├─ Filter (exclude_servers, exclude_sections, protocols)
  │
  └─ Generate + Write per target
      ├─ Cursor:       mcp.json + project.mdc (MDC frontmatter)
      ├─ Codex:        config.toml (marker-based) + AGENTS.md
      └─ Antigravity:  mcp_config.json (stdio-only)
```

## Adding an Adapter

agentsync is designed for extension. To add support for a new AI agent:

1. Create `src/agentsync/adapters/youragent.py` — implement `TargetAdapter`
2. Register it in `cli.py` (`create_targets`)
3. Add the type to `KNOWN_TARGET_TYPES` in `config.py`
4. Write tests in `tests/test_adapter_youragent.py`
5. Update this README

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines and the full adapter interface.

## Roadmap

| Version | Focus |
|---------|-------|
| **v0.1** | Core sync: Claude → Cursor, Codex, Antigravity |
| **v0.2** | Plugin system for custom adapters |
| **v0.3** | Watch mode (auto-sync on file change) |
| **v0.4** | Windsurf, Zed, Cline adapters (community) |
| **v1.0** | Stable API, full coverage |

Have an idea? [Open a discussion](https://github.com/spyrae/agentsync/discussions) or [request an adapter](https://github.com/spyrae/agentsync/issues/new?template=new_adapter.yml).

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Please review our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## License

[MIT](LICENSE)
