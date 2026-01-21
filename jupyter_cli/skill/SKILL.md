---
name: jupyter-cli
description: Use jupyter-cli for programmatic Jupyter notebook execution with persistent kernels. Invoke when working with .ipynb files, needing to run notebook cells, or managing Jupyter kernels.
allowed-tools: Bash(jupyter-cli:*), Read, Glob, Grep
---

# jupyter-cli: Programmatic Jupyter Notebook Execution

You have access to `jupyter-cli`, a CLI tool for executing Jupyter notebook cells with persistent kernels. This allows you to run expensive setup cells once and iterate on later cells without re-running setup.

## Installation

If not installed, run:
```bash
pip install jupyter-cli
```

## Quick Reference

```bash
# Start kernel (required before exec)
jupyter-cli start notebook.ipynb

# Execute cells (0-indexed)
jupyter-cli exec notebook.ipynb 0 1 2

# Stop kernel when done
jupyter-cli stop notebook.ipynb
```

## Core Concept

The tool maintains a **persistent kernel** that survives between CLI invocations:
- Run expensive setup cells once (DB connections, model loading)
- Iterate on later cells without re-running setup
- Variables persist across separate `exec` calls

## Commands

### Exploring Notebooks (Token-Efficient)

**List cells** - Get a quick overview:
```bash
jupyter-cli list notebook.ipynb
# [0] code: x = 10
# [1] code: y = x * 2
# [2] markdown: ## Results
```

**Filter by type**:
```bash
jupyter-cli list notebook.ipynb --code      # Only code cells
jupyter-cli list notebook.ipynb --markdown  # Only markdown
jupyter-cli list notebook.ipynb --range 0-10  # First 11 cells
```

**Read full cell source**:
```bash
jupyter-cli read notebook.ipynb 5 6 7       # Specific cells
jupyter-cli read notebook.ipynb --code      # All code cells
jupyter-cli read notebook.ipynb --range 50-60  # Range of cells
```

**Search for patterns**:
```bash
jupyter-cli search notebook.ipynb "DataFrame"
jupyter-cli search notebook.ipynb "def.*train" --regex
jupyter-cli search notebook.ipynb "TODO" --markdown
```

### Kernel Management

**Start a kernel**:
```bash
jupyter-cli start notebook.ipynb
# Kernel started. ID: abc123
```

**Check status**:
```bash
jupyter-cli status notebook.ipynb  # Specific notebook
jupyter-cli status                 # All kernels
```

**Stop kernel**:
```bash
jupyter-cli stop notebook.ipynb
jupyter-cli stop --all  # Stop all kernels
```

### Executing Cells

**Run specific cells** (0-indexed):
```bash
jupyter-cli exec notebook.ipynb 0        # Single cell
jupyter-cli exec notebook.ipynb 0 1 2 3  # Multiple cells
jupyter-cli exec notebook.ipynb 50 51    # Later cells only
```

**Options**:
```bash
jupyter-cli exec notebook.ipynb 5 --timeout 300  # 5 min timeout
jupyter-cli exec notebook.ipynb 5 --quiet        # Suppress output
```

### Reading Outputs

**View stored outputs** (from previous notebook runs):
```bash
jupyter-cli outputs notebook.ipynb 5
jupyter-cli outputs notebook.ipynb --range 10-20
```

## Common Workflows

### 1. Exploring an Unknown Notebook

```bash
# Get overview
jupyter-cli list notebook.ipynb

# Check what code cells exist
jupyter-cli list notebook.ipynb --code

# Search for key functionality
jupyter-cli search notebook.ipynb "train"
jupyter-cli search notebook.ipynb "import"

# Read specific cells of interest
jupyter-cli read notebook.ipynb 0 1 2
```

### 2. Running a Data Science Notebook

```bash
# Start kernel
jupyter-cli start analysis.ipynb

# Run setup cells (imports, data loading)
jupyter-cli exec analysis.ipynb 0 1 2 3 4

# Run analysis
jupyter-cli exec analysis.ipynb 10 11 12

# Iterate on visualization cell
jupyter-cli exec analysis.ipynb 15
# ... make changes to cell 15 ...
jupyter-cli exec analysis.ipynb 15  # Re-run with preserved state

# Clean up
jupyter-cli stop analysis.ipynb
```

### 3. Debugging a Failed Cell

```bash
# Check what the cell does
jupyter-cli read notebook.ipynb 42

# Check previous outputs
jupyter-cli outputs notebook.ipynb 40 41

# Search for related code
jupyter-cli search notebook.ipynb "variable_name"

# Run cells leading up to failure
jupyter-cli exec notebook.ipynb 38 39 40 41
jupyter-cli exec notebook.ipynb 42  # See current error
```

## Token Efficiency Tips

1. **Use `list` first** - One line per cell vs reading entire notebook
2. **Use `--code` filter** - Skip markdown when looking for logic
3. **Use `--range`** - Only read the section you need
4. **Use `search`** - Find relevant cells without reading everything
5. **Avoid raw .ipynb** - JSON structure wastes tokens on metadata

**Token comparison** for a 50-cell notebook:
- Raw .ipynb file: ~50,000+ tokens
- `jupyter-cli list`: ~500 tokens
- `jupyter-cli read --code`: ~2,000 tokens

## Error Handling

**No kernel running**:
```
Error: No kernel found for notebook: notebook.ipynb
Hint: Run 'jupyter-cli start <notebook>' first
```

**Invalid cell index**:
```
Error: Cell index 999 out of range (notebook has 50 cells)
```

## Best Practices

1. **Always start with `list`** to understand notebook structure
2. **Use `search` before reading** to find relevant cells
3. **Start kernel before exec** - `exec` won't auto-start
4. **Stop kernel when done** - Clean up resources
5. **Use `--timeout` for long cells** - Default is 600s (10 min)

## Limitations

- **No rich output display** - Images show as `[Image: PNG]`
- **No interactive widgets** - ipywidgets won't work
- **No cell editing** - Use an external editor to modify .ipynb
