# Contributing to agentsync

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/spyrae/agentsync.git
cd agentsync
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest                  # All tests
pytest -v               # Verbose
pytest --cov=agentsync  # With coverage
```

## Code Quality

```bash
ruff check src/ tests/          # Lint
ruff format src/ tests/         # Format
mypy src/agentsync/             # Type check
```

All three must pass before merging. CI runs these automatically.

## Pre-commit Hooks (optional)

```bash
pip install pre-commit
pre-commit install
```

This runs ruff on every commit.

## Making Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes
4. Ensure tests pass and coverage doesn't drop
5. Open a pull request against `main`

### Commit Messages

Use conventional-ish format:

```
feat: add Windsurf adapter
fix: handle empty mcpServers in global config
test: add integration test for dry-run mode
docs: update CLI reference in README
```

## Adding a New Adapter

See the "Adding Adapters" section in the README for the architecture overview.

Steps:

1. Create `src/agentsync/adapters/youragent.py`
2. Implement `TargetAdapter` (or `SourceAdapter`)
3. Register it in `cli.py` (`create_targets` / `create_source`)
4. Add the type to `KNOWN_TARGET_TYPES` in `config.py`
5. Write tests in `tests/test_adapter_youragent.py`
6. Update README with the new agent in the "Supported Agents" table

## Project Structure

```
src/agentsync/
├── adapters/       # Source and target adapters
│   ├── base.py     # Abstract base classes
│   ├── claude.py   # Claude Code source adapter
│   ├── cursor.py   # Cursor target adapter
│   ├── codex.py    # Codex target adapter
│   └── antigravity.py  # Antigravity/Gemini target adapter
├── utils/          # Shared utilities
│   ├── backup.py   # File backup
│   ├── dedup.py    # Case-insensitive deduplication
│   ├── diff.py     # Server diff display
│   ├── io.py       # File writing with WriteResult
│   ├── logger.py   # Rich console logging
│   ├── markdown.py # Markdown section parsing
│   └── output.py   # CLI output formatting
├── cli.py          # Click CLI commands
├── config.py       # YAML config loading
├── sync.py         # Sync orchestrator
└── validate.py     # Validation orchestrator
```

## Code Style

- Python 3.9+ compatible (use `from __future__ import annotations`)
- Ruff for linting and formatting (config in `pyproject.toml`)
- Type hints everywhere, checked by mypy
- Tests use pytest with `tmp_path` fixtures — no real user files

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
