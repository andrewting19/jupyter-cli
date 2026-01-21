# jupyter-cli

[![PyPI version](https://badge.fury.io/py/jupyter-cli.svg)](https://pypi.org/project/jupyter-cli/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Programmatic Jupyter notebook cell execution with persistent kernels.

## The Problem

Existing Jupyter tools don't support selective cell execution with persistent state:
- **papermill/nbconvert/nbexec**: Run entire notebooks
- **jupyter console**: Requires manual interaction
- **nbclient**: Kernel dies when Python process exits

**jupyter-cli** fills this gap: execute specific cells while keeping kernel state alive between CLI invocations.

## Use Case

A data science notebook with ~60 cells:
- Cells 1-49: Expensive setup (DB queries, model training) - takes ~20 minutes
- Cells 50+: Experimental iterations

**With jupyter-cli:**
```bash
jupyter-cli start notebook.ipynb
jupyter-cli exec notebook.ipynb 0 1 2 ... 49  # Run setup once
jupyter-cli exec notebook.ipynb 50            # Iterate on cell 50
jupyter-cli exec notebook.ipynb 50            # Again, without re-running setup
jupyter-cli stop notebook.ipynb
```

## Installation

```bash
pip install jupyter-cli

# Or from source
git clone https://github.com/andrewting19/jupyter-cli.git
cd jupyter-cli
pip install -e .
```

**Requirements:**
- Python 3.8+
- jupyter_client
- nbformat
- click

## Quick Start

```bash
# Start a persistent kernel
jupyter-cli start notebook.ipynb

# Execute cells (0-indexed)
jupyter-cli exec notebook.ipynb 0 1 2

# Run inline code (no cell needed)
jupyter-cli run notebook.ipynb "print(df.shape)"

# Stop the kernel
jupyter-cli stop notebook.ipynb
```

## Commands

### Kernel Management

| Command | Description |
|---------|-------------|
| `start <notebook>` | Start persistent kernel |
| `stop <notebook>` | Stop kernel |
| `stop --all` | Stop all kernels |
| `status [notebook]` | Check kernel status |

### Cell Execution

| Command | Description |
|---------|-------------|
| `exec <notebook> <cells...>` | Execute specific cells |
| `exec <notebook> --all` | Execute all code cells |
| `exec <notebook> --range 0-10` | Execute cell range |
| `exec <notebook> 0 --quiet` | Suppress output |

### Inline Code Execution

| Command | Description |
|---------|-------------|
| `run <notebook> "code"` | Execute arbitrary code on kernel |
| `run <notebook> --file script.py` | Execute code from file (best for complex code) |
| `run <notebook> -` | Read code from stdin |
| `run <notebook> "code" --quiet` | Suppress output |

### Notebook Exploration

| Command | Description |
|---------|-------------|
| `list <notebook>` | List all cells with preview |
| `list <notebook> --code` | Only code cells |
| `list <notebook> --range 0-10` | Cell range |
| `read <notebook> 0 1 2` | Read full cell source |
| `read <notebook> --code` | Read all code cells |
| `search <notebook> "pattern"` | Search cells |
| `search <notebook> "regex" -r` | Regex search |
| `outputs <notebook> 5` | Read stored outputs |
| `info <notebook>` | Notebook info |

## Examples

### Exploring a Notebook

```bash
# Quick overview
$ jupyter-cli list notebook.ipynb
[0] code: import pandas as pd
[1] code: df = pd.read_csv('data.csv')
[2] code: df.head()
[3] markdown: ## Data Cleaning
[4] code: df = df.dropna()
...

# Find all cells using DataFrame
$ jupyter-cli search notebook.ipynb "DataFrame"
Found 3 match(es):
[5] code: df = pd.DataFrame(data)
[12] code: result = DataFrame.from_dict(...)
[45] code: final_df = pd.DataFrame(results)

# Read specific cells
$ jupyter-cli read notebook.ipynb 5 12
=== Cell 5 (code) ===
df = pd.DataFrame(data)
print(df.shape)

=== Cell 12 (code) ===
result = DataFrame.from_dict(processed_data)
```

### Selective Execution

```bash
# Start kernel
$ jupyter-cli start analysis.ipynb
Kernel started. ID: abc123

# Run expensive setup
$ jupyter-cli exec analysis.ipynb 0 1 2 3 4 5
[Cell 0] Executing: import pandas as pd...
[Cell 1] Executing: df = load_data()...
Loading 1M rows from database...
...

# Iterate on experiment cell
$ jupyter-cli exec analysis.ipynb 50
[Cell 50] Executing: model.fit(X, y)...
Accuracy: 0.85

# Edit cell 50 in your editor, then re-run
$ jupyter-cli exec analysis.ipynb 50
[Cell 50] Executing: model.fit(X, y, epochs=100)...
Accuracy: 0.92

# Clean up
$ jupyter-cli stop analysis.ipynb
Kernel stopped.
```

### Inline Code Execution

```bash
# After running setup cells, inspect variables without modifying notebook
$ jupyter-cli run analysis.ipynb "df.shape"
[inline] Executing: df.shape
(10000, 25)

$ jupyter-cli run analysis.ipynb "df.columns.tolist()"
[inline] Executing: df.columns.tolist()
['id', 'name', 'price', 'category', ...]

# For complex/multiline code, use --file to avoid shell escaping issues
$ cat > /tmp/analysis.py << 'EOF'
for col in df.select_dtypes(include='number').columns:
    print(f"{col}: mean={df[col].mean():.2f}, std={df[col].std():.2f}")
EOF
$ jupyter-cli run analysis.ipynb --file /tmp/analysis.py
[inline] Executing: for col in df.select_dtypes(include='number').columns:...
price: mean=149.99, std=75.23
quantity: mean=2.5, std=1.2
...

# Debug: see what's in scope
$ jupyter-cli run analysis.ipynb "list(locals().keys())"
[inline] Executing: list(locals().keys())
['df', 'model', 'X_train', 'y_train', ...]
```

### Reading Previous Outputs

```bash
$ jupyter-cli outputs notebook.ipynb --range 10-15
=== Cell 10 output ===
[stdout] Training model...
[stdout] Epoch 1/10: loss=0.5

=== Cell 12 output ===
[result] 0.923456

=== Cell 14 output ===
[error] ValueError: invalid shape
```

## Gap Analysis: CLI vs Manual Jupyter

| Feature | jupyter-cli | Manual Jupyter UI |
|---------|-------------|-------------------|
| Cell execution | Yes | Yes |
| Persistent kernel | Yes | Yes |
| Execute specific cells | Yes | Yes |
| State persistence | Yes | Yes |
| stdout/stderr output | Yes | Yes |
| Rich output (HTML) | Truncated | Full rendering |
| Image output | `[Image: PNG]` | Displayed |
| Interactive widgets | No | Yes |
| Cell editing | No (use external editor) | Yes |
| Magic commands | Yes (via kernel) | Yes |
| Auto-complete | No | Yes |
| Inline plots | No (shows placeholder) | Yes |
| Syntax highlighting | No | Yes |
| Variable inspector | No | Extension available |
| Debugging | No | Yes |
| Multiple kernels | Yes (one per notebook) | Yes |

**Key takeaway:** jupyter-cli is for **programmatic automation**, not interactive development. Use it when you need:
- Scripted notebook execution
- LLM agent integration
- CI/CD pipelines
- Selective cell re-execution without re-running setup

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌────────────┐
│  CLI Client │────▶│  Daemon Process  │────▶│   Kernel   │
└─────────────┘     └──────────────────┘     └────────────┘
      │                     │                       │
      │  connection.json    │  keeps alive          │  Python
      │◀────────────────────│                       │  process
      │                     │                       │
      └─────────────────────┴───────────────────────┘
```

1. **Daemon Process**: Starts kernel, keeps it alive, writes connection file
2. **CLI Client**: Reads notebook, connects to kernel via connection file, executes cells

## For LLM Agents

See [CLAUDE.md](CLAUDE.md) for a comprehensive guide on using jupyter-cli with LLM agents, including:
- Token-efficient exploration strategies
- Common workflows
- Best practices

### Claude Code Skill

If you're using [Claude Code](https://claude.ai/claude-code), you can install the jupyter-cli skill to teach Claude how to use this tool:

```bash
# Install the skill (interactive prompt for global vs local)
jupyter-cli install-skill

# Or specify directly:
jupyter-cli install-skill --global   # Available in all projects
jupyter-cli install-skill --local    # Current directory only
```

After installation, restart Claude Code. The skill will:
- Automatically activate when working with Jupyter notebooks
- Be available via `/jupyter-cli` command
- Teach Claude the proper commands and best practices

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run specific test class
pytest tests/test_jupyter_cli.py::TestCLIExec -v
```

## License

MIT
