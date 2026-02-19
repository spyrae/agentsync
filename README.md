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

## Quick Start

```bash
pip install agentsync
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

```bash
agentsync sync              # Full sync (MCP + rules)
agentsync sync --dry-run    # Preview changes
agentsync sync --mcp-only   # Only MCP servers
agentsync sync --rules-only # Only rules
agentsync sync -t cursor    # Sync specific target

agentsync validate          # Full validation
agentsync validate -v       # Verbose output

agentsync init              # Create config file
agentsync status            # Show sync state
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
