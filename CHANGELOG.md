# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-02-20

### Added

- Initial release
- **Config system**: YAML config loading with validation, path resolution, auto-discovery
- **Claude source adapter**: 3-tier MCP server merge (global, project, local .mcp.json), Markdown rules parsing
- **Cursor target adapter**: JSON MCP config, MDC rules with YAML frontmatter
- **Codex target adapter**: TOML MCP config with marker-based insertion, preserves existing config sections
- **Antigravity target adapter**: JSON MCP config with stdio-only protocol filtering
- **Sync engine**: source → dedup → filter → generate → write pipeline
- **Validation engine**: server consistency, excluded section leak detection, case-insensitive duplicate check
- **CLI commands**: `sync`, `validate`, `init`, `status` via Click
- **Rich output**: coloured sync summary, validation report, status display
- **Utilities**: case-insensitive dedup, file backup, server diff, Markdown section parser
- **Test suite**: 192 tests, 97% coverage
- **CI/CD**: GitHub Actions (lint + test matrix + build), PyPI release workflow, Dependabot

[Unreleased]: https://github.com/spyrae/agentsync/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/spyrae/agentsync/releases/tag/v0.1.0
