# Contributing to jupyter-cli

## Development Setup

```bash
# Clone the repo
git clone https://github.com/andrewting19/jupyter-cli.git
cd jupyter-cli

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_jupyter_cli.py -v

# With coverage
pytest tests/ -v --cov=jupyter_cli
```

## Code Style

- Follow PEP 8
- Use type hints where practical
- Keep functions focused and well-documented

## Releasing to PyPI

### Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org
2. **API Token**: Generate a token at https://pypi.org/manage/account/token/
3. **Build Tools**: `pip install build twine`

### Release Process

We have an automated release script:

```bash
# Patch release (0.1.2 -> 0.1.3)
./scripts/release.sh patch

# Minor release (0.1.2 -> 0.2.0)
./scripts/release.sh minor

# Major release (0.1.2 -> 1.0.0)
./scripts/release.sh major

# Specific version
./scripts/release.sh 1.0.0
```

The script will:
1. Update version in `pyproject.toml` and `jupyter_cli/__init__.py`
2. Build the package
3. Upload to PyPI
4. Create a git commit and tag

### Manual Release

If you prefer to release manually:

```bash
# 1. Update version in both files:
#    - pyproject.toml: version = "X.Y.Z"
#    - jupyter_cli/__init__.py: __version__ = "X.Y.Z"

# 2. Clean and build
rm -rf dist/ build/
python -m build

# 3. Upload to PyPI
twine upload dist/* -u __token__ -p $PYPI_TOKEN

# 4. Commit and tag
git add pyproject.toml jupyter_cli/__init__.py
git commit -m "Release vX.Y.Z"
git tag -a "vX.Y.Z" -m "Release vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

### Setting Up PyPI Token

**Option 1: Environment Variable**
```bash
export PYPI_TOKEN="pypi-xxxxx..."
./scripts/release.sh patch
```

**Option 2: ~/.pypirc file**
```ini
[pypi]
username = __token__
password = pypi-xxxxx...
```

## Project Structure

```
jupyter-cli/
├── jupyter_cli/           # Main package
│   ├── __init__.py        # Version string
│   ├── cli.py             # CLI entry points
│   ├── client.py          # Kernel client
│   ├── daemon.py          # Kernel daemon management
│   ├── notebook.py        # Notebook parsing
│   └── skill/             # Claude Code skill
│       └── SKILL.md
├── tests/                 # Test suite
├── scripts/               # Automation scripts
│   └── release.sh         # Release automation
├── pyproject.toml         # Package config (version here!)
├── README.md
├── CLAUDE.md              # LLM agent guide
└── CONTRIBUTING.md        # This file
```

## Version Management

Version is stored in two places (must be kept in sync):
- `pyproject.toml` - Package version for PyPI
- `jupyter_cli/__init__.py` - Runtime version for `--version` flag

The release script handles syncing these automatically.
