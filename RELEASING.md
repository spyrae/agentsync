# Releasing agentsync

## Prerequisites

- PyPI Trusted Publisher configured for `spyrae/agentsync` repo
- GitHub environment `pypi` created in repo settings

## Release Process

1. **Update version** in `src/agentsync/__init__.py`:
   ```python
   __version__ = "0.2.0"
   ```

2. **Update CHANGELOG.md** — move items from `[Unreleased]` to new version section

3. **Update pyproject.toml** version (keep in sync with `__init__.py`):
   ```toml
   version = "0.2.0"
   ```

4. **Commit and tag**:
   ```bash
   git add -A
   git commit -m "release: v0.2.0"
   git tag v0.2.0
   git push origin main --tags
   ```

5. **GitHub Actions** will automatically:
   - Build sdist + wheel
   - Publish to PyPI via trusted publisher (OIDC, no tokens)
   - Create GitHub Release with auto-generated notes

6. **Verify**:
   ```bash
   pip install agentsync-cli==0.2.0
   agentsync --version
   ```

## First-Time PyPI Setup

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new pending publisher:
   - **PyPI Project Name**: `agentsync-cli`
   - **Owner**: `spyrae`
   - **Repository name**: `agentsync`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`
3. The first release will claim the package name

## TestPyPI (optional)

To test before real release:

```bash
pip install build twine
python -m build
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ agentsync
```
