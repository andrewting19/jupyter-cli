"""Notebook parsing utilities."""

import nbformat
from pathlib import Path
from typing import List, Optional


def read_notebook(notebook_path: str) -> nbformat.NotebookNode:
    """Read a Jupyter notebook from disk."""
    path = Path(notebook_path)
    if not path.exists():
        raise FileNotFoundError(f"Notebook not found: {notebook_path}")
    if not path.suffix == ".ipynb":
        raise ValueError(f"Not a notebook file: {notebook_path}")
    return nbformat.read(path, as_version=4)


def get_cell_source(notebook: nbformat.NotebookNode, index: int) -> str:
    """Get the source code of a cell by index."""
    if index < 0 or index >= len(notebook.cells):
        raise IndexError(f"Cell index {index} out of range (notebook has {len(notebook.cells)} cells)")
    return notebook.cells[index].source


def get_cell_type(notebook: nbformat.NotebookNode, index: int) -> str:
    """Get the type of a cell by index (code, markdown, raw)."""
    if index < 0 or index >= len(notebook.cells):
        raise IndexError(f"Cell index {index} out of range (notebook has {len(notebook.cells)} cells)")
    return notebook.cells[index].cell_type


def get_code_cells(notebook: nbformat.NotebookNode) -> List[int]:
    """Get indices of all code cells in the notebook."""
    return [i for i, cell in enumerate(notebook.cells) if cell.cell_type == "code"]


def get_cell_count(notebook: nbformat.NotebookNode) -> int:
    """Get the total number of cells in the notebook."""
    return len(notebook.cells)


def validate_cell_indices(notebook: nbformat.NotebookNode, indices: List[int]) -> Optional[str]:
    """Validate that all cell indices are valid. Returns error message or None."""
    cell_count = len(notebook.cells)
    for idx in indices:
        if idx < 0 or idx >= cell_count:
            return f"Cell index {idx} out of range (notebook has {cell_count} cells)"
    return None
