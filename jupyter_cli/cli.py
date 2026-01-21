"""CLI entry point for jupyter-cli."""

import sys
from pathlib import Path

import click

from . import __version__
from .daemon import (
    start_kernel_daemon,
    stop_kernel,
    stop_all_kernels,
    load_kernel_info,
    is_kernel_alive,
    list_all_kernels,
)
from .client import execute_cells, KernelNotRunningError
from .notebook import read_notebook, get_cell_count, get_code_cells


@click.group()
@click.version_option(version=__version__)
def main():
    """jupyter-cli: Programmatic Jupyter cell execution with persistent kernels."""
    pass


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--kernel", "-k", default="python3", help="Kernel name to use (default: python3)")
def start(notebook: str, kernel: str):
    """Start a persistent kernel for a notebook.

    NOTEBOOK is the path to the .ipynb file.
    """
    notebook_path = str(Path(notebook).resolve())

    # Validate it's a notebook
    try:
        nb = read_notebook(notebook_path)
        cell_count = get_cell_count(nb)
        code_cells = len(get_code_cells(nb))
    except Exception as e:
        click.echo(f"Error reading notebook: {e}", err=True)
        sys.exit(1)

    click.echo(f"Starting kernel for: {notebook}")
    click.echo(f"Notebook has {cell_count} cells ({code_cells} code cells)")

    result = start_kernel_daemon(notebook_path, kernel_name=kernel)

    if result["status"] == "started":
        click.echo(f"Kernel started. ID: {result['kernel_id']}")
        click.echo(f"PID: {result['pid']}")
    elif result["status"] == "already_running":
        click.echo(f"Kernel already running. ID: {result['kernel_id']}")
        click.echo(f"PID: {result['pid']}")
    else:
        click.echo(f"Error: {result.get('message', 'Unknown error')}", err=True)
        sys.exit(1)


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.argument("cells", nargs=-1, type=int, required=True)
@click.option("--timeout", "-t", default=600, help="Timeout per cell in seconds (default: 600)")
@click.option("--quiet", "-q", is_flag=True, help="Suppress output")
def exec(notebook: str, cells: tuple, timeout: int, quiet: bool):
    """Execute specific cells from a notebook.

    NOTEBOOK is the path to the .ipynb file.
    CELLS are the cell indices to execute (0-indexed).

    Examples:
        jupyter-cli exec notebook.ipynb 0 1 2
        jupyter-cli exec notebook.ipynb 50 51 52 --timeout 300
    """
    notebook_path = str(Path(notebook).resolve())
    cell_indices = list(cells)

    try:
        results = execute_cells(
            notebook_path,
            cell_indices,
            timeout=timeout,
            verbose=not quiet,
        )

        # Check for errors
        errors = [r for r in results if r.get("status") == "error"]
        if errors:
            sys.exit(1)

    except KernelNotRunningError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Hint: Run 'jupyter-cli start <notebook>' first", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error executing cells: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("notebook", type=click.Path(exists=True), required=False)
def status(notebook: str = None):
    """Check kernel status.

    If NOTEBOOK is provided, shows status for that notebook's kernel.
    Otherwise, shows status of all known kernels.
    """
    if notebook:
        notebook_path = str(Path(notebook).resolve())
        info = load_kernel_info(notebook_path)

        if not info:
            click.echo("No kernel found for this notebook")
            return

        alive = is_kernel_alive(info)
        status_str = "running" if alive else "not running"

        click.echo(f"Kernel {info['kernel_id']} {status_str}")
        click.echo(f"  PID: {info['pid']}")
        click.echo(f"  Notebook: {info['notebook_path']}")
        click.echo(f"  Connection: {info['connection_file']}")

    else:
        kernels = list_all_kernels()
        if not kernels:
            click.echo("No kernels found")
            return

        click.echo(f"Found {len(kernels)} kernel(s):")
        for info in kernels:
            status_str = "running" if info.get("alive") else "stopped"
            click.echo(f"  [{status_str}] {info['kernel_id']} (pid {info['pid']})")
            click.echo(f"           {info['notebook_path']}")


@main.command()
@click.argument("notebook", type=click.Path(exists=True), required=False)
@click.option("--all", "-a", "stop_all", is_flag=True, help="Stop all kernels")
def stop(notebook: str = None, stop_all: bool = False):
    """Stop a running kernel.

    If NOTEBOOK is provided, stops the kernel for that notebook.
    Use --all to stop all running kernels.
    """
    if stop_all:
        result = stop_all_kernels()
        if result["stopped"] == 0:
            click.echo("No running kernels to stop")
        else:
            click.echo(f"Stopped {result['stopped']} kernel(s)")
        return

    if not notebook:
        click.echo("Error: Provide a notebook path or use --all", err=True)
        sys.exit(1)

    notebook_path = str(Path(notebook).resolve())
    result = stop_kernel(notebook_path)

    if result["status"] == "stopped":
        click.echo(f"Kernel stopped. ID: {result['kernel_id']}")
    elif result["status"] == "not_found":
        click.echo("No kernel found for this notebook")
    elif result["status"] == "not_running":
        click.echo(result["message"])
    else:
        click.echo(f"Error: {result.get('message', 'Unknown error')}", err=True)
        sys.exit(1)


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
def info(notebook: str):
    """Show information about a notebook.

    Displays cell count and indices of code cells.
    """
    notebook_path = str(Path(notebook).resolve())

    try:
        nb = read_notebook(notebook_path)
        cell_count = get_cell_count(nb)
        code_cells = get_code_cells(nb)

        click.echo(f"Notebook: {notebook}")
        click.echo(f"Total cells: {cell_count}")
        click.echo(f"Code cells: {len(code_cells)}")

        if code_cells:
            click.echo(f"Code cell indices: {', '.join(map(str, code_cells))}")

        # Check kernel status
        info = load_kernel_info(notebook_path)
        if info and is_kernel_alive(info):
            click.echo(f"Kernel: running (pid {info['pid']})")
        else:
            click.echo("Kernel: not running")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def parse_range(range_str: str, max_index: int) -> list[int]:
    """Parse a range string like '0-10' or '50-' into list of indices."""
    if "-" not in range_str:
        raise ValueError(f"Invalid range format: {range_str}")

    parts = range_str.split("-", 1)
    start_str, end_str = parts

    start = int(start_str) if start_str else 0
    end = int(end_str) if end_str else max_index

    if start < 0:
        start = 0
    if end > max_index:
        end = max_index
    if start > end:
        raise ValueError(f"Invalid range: start ({start}) > end ({end})")

    return list(range(start, end + 1))


def get_first_line(source: str, max_len: int = 60) -> str:
    """Get first non-empty line of source, truncated."""
    for line in source.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            if len(line) > max_len:
                return line[:max_len] + "..."
            return line
    # If all lines are comments or empty, return first non-empty
    for line in source.split("\n"):
        line = line.strip()
        if line:
            if len(line) > max_len:
                return line[:max_len] + "..."
            return line
    return ""


@main.command("list")
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--code", "only_code", is_flag=True, help="Only list code cells")
@click.option("--markdown", "only_markdown", is_flag=True, help="Only list markdown cells")
@click.option("--range", "cell_range", type=str, help="Cell range (e.g., '0-10', '50-')")
def list_cells(notebook: str, only_code: bool, only_markdown: bool, cell_range: str):
    """List all cells with index, type, and first line preview.

    Token-efficient overview for LLM agents.

    Examples:
        jupyter-cli list notebook.ipynb
        jupyter-cli list notebook.ipynb --code
        jupyter-cli list notebook.ipynb --range 0-20
    """
    notebook_path = str(Path(notebook).resolve())

    try:
        nb = read_notebook(notebook_path)
        total_cells = len(nb.cells)

        # Determine which indices to show
        if cell_range:
            indices = parse_range(cell_range, total_cells - 1)
        else:
            indices = list(range(total_cells))

        for idx in indices:
            if idx >= total_cells:
                continue

            cell = nb.cells[idx]
            cell_type = cell.cell_type

            # Apply filters
            if only_code and cell_type != "code":
                continue
            if only_markdown and cell_type != "markdown":
                continue

            first_line = get_first_line(cell.source)
            click.echo(f"[{idx}] {cell_type}: {first_line}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.argument("cells", nargs=-1, type=int)
@click.option("--code", "only_code", is_flag=True, help="Only read code cells")
@click.option("--markdown", "only_markdown", is_flag=True, help="Only read markdown cells")
@click.option("--range", "cell_range", type=str, help="Cell range (e.g., '0-10', '50-')")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def read(notebook: str, cells: tuple, only_code: bool, only_markdown: bool,
         cell_range: str, as_json: bool):
    """Read full content of specific cells.

    Provide cell indices as arguments, or use --range or --code/--markdown filters.

    Examples:
        jupyter-cli read notebook.ipynb 0 1 2
        jupyter-cli read notebook.ipynb --code
        jupyter-cli read notebook.ipynb --range 50-60
        jupyter-cli read notebook.ipynb --code --range 0-20
    """
    import json as json_module

    notebook_path = str(Path(notebook).resolve())

    try:
        nb = read_notebook(notebook_path)
        total_cells = len(nb.cells)

        # Determine which indices to read
        if cells:
            # Explicit cell indices provided
            indices = list(cells)
        elif cell_range:
            indices = parse_range(cell_range, total_cells - 1)
        elif only_code or only_markdown:
            # Filter all cells
            indices = list(range(total_cells))
        else:
            click.echo("Error: Provide cell indices, --range, or --code/--markdown filter", err=True)
            sys.exit(1)

        # Collect cells to output
        output_cells = []
        for idx in indices:
            if idx < 0 or idx >= total_cells:
                click.echo(f"Warning: Cell {idx} out of range (0-{total_cells-1})", err=True)
                continue

            cell = nb.cells[idx]
            cell_type = cell.cell_type

            # Apply filters
            if only_code and cell_type != "code":
                continue
            if only_markdown and cell_type != "markdown":
                continue

            output_cells.append({
                "index": idx,
                "type": cell_type,
                "source": cell.source,
            })

        if as_json:
            click.echo(json_module.dumps(output_cells, indent=2))
        else:
            for i, cell_data in enumerate(output_cells):
                if i > 0:
                    click.echo()  # Blank line between cells
                click.echo(f"=== Cell {cell_data['index']} ({cell_data['type']}) ===")
                click.echo(cell_data["source"])

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.argument("pattern", type=str)
@click.option("--regex", "-r", is_flag=True, help="Treat pattern as regex")
@click.option("--code", "only_code", is_flag=True, help="Only search code cells")
@click.option("--markdown", "only_markdown", is_flag=True, help="Only search markdown cells")
@click.option("--context", "-C", type=int, default=0, help="Lines of context around match")
def search(notebook: str, pattern: str, regex: bool, only_code: bool,
           only_markdown: bool, context: int):
    """Search for pattern in notebook cells.

    Shows matching cells with the first matching line.

    Examples:
        jupyter-cli search notebook.ipynb "DataFrame"
        jupyter-cli search notebook.ipynb "def.*train" --regex
        jupyter-cli search notebook.ipynb "TODO" --markdown
    """
    import re

    notebook_path = str(Path(notebook).resolve())

    try:
        nb = read_notebook(notebook_path)

        if regex:
            try:
                compiled = re.compile(pattern)
            except re.error as e:
                click.echo(f"Invalid regex: {e}", err=True)
                sys.exit(1)

        matches = []
        for idx, cell in enumerate(nb.cells):
            cell_type = cell.cell_type

            # Apply filters
            if only_code and cell_type != "code":
                continue
            if only_markdown and cell_type != "markdown":
                continue

            source = cell.source

            # Check for match
            if regex:
                if compiled.search(source):
                    # Find matching line
                    for line_num, line in enumerate(source.split("\n")):
                        if compiled.search(line):
                            matches.append({
                                "index": idx,
                                "type": cell_type,
                                "line_num": line_num,
                                "line": line.strip(),
                                "source": source,
                            })
                            break
            else:
                if pattern.lower() in source.lower():
                    # Find matching line (case-insensitive)
                    for line_num, line in enumerate(source.split("\n")):
                        if pattern.lower() in line.lower():
                            matches.append({
                                "index": idx,
                                "type": cell_type,
                                "line_num": line_num,
                                "line": line.strip(),
                                "source": source,
                            })
                            break

        if not matches:
            click.echo("No matches found")
            return

        click.echo(f"Found {len(matches)} match(es):")
        for match in matches:
            line_preview = match["line"][:70] + "..." if len(match["line"]) > 70 else match["line"]
            click.echo(f"[{match['index']}] {match['type']}: {line_preview}")

            if context > 0:
                lines = match["source"].split("\n")
                line_num = match["line_num"]
                start = max(0, line_num - context)
                end = min(len(lines), line_num + context + 1)
                for i in range(start, end):
                    marker = ">" if i == line_num else " "
                    click.echo(f"  {marker} {lines[i]}")
                click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def format_cell_output(output: dict) -> str:
    """Format a cell output for display."""
    output_type = output.get("output_type", "")

    if output_type == "stream":
        name = output.get("name", "stdout")
        text = "".join(output.get("text", []))
        return f"[{name}] {text.rstrip()}"

    elif output_type == "execute_result":
        data = output.get("data", {})
        if "text/plain" in data:
            text = "".join(data["text/plain"]) if isinstance(data["text/plain"], list) else data["text/plain"]
            return f"[result] {text.rstrip()}"
        return f"[result] {list(data.keys())}"

    elif output_type == "display_data":
        data = output.get("data", {})
        if "text/plain" in data:
            text = "".join(data["text/plain"]) if isinstance(data["text/plain"], list) else data["text/plain"]
            return f"[display] {text.rstrip()}"
        elif "image/png" in data:
            return "[display] <image/png>"
        return f"[display] {list(data.keys())}"

    elif output_type == "error":
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        return f"[error] {ename}: {evalue}"

    return f"[{output_type}]"


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.argument("cells", nargs=-1, type=int)
@click.option("--range", "cell_range", type=str, help="Cell range (e.g., '0-10', '50-')")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def outputs(notebook: str, cells: tuple, cell_range: str, as_json: bool):
    """Read cell outputs (from last notebook execution).

    Shows outputs stored in the notebook file from previous runs.

    Examples:
        jupyter-cli outputs notebook.ipynb 5
        jupyter-cli outputs notebook.ipynb 0 1 2
        jupyter-cli outputs notebook.ipynb --range 10-20
    """
    import json as json_module

    notebook_path = str(Path(notebook).resolve())

    try:
        nb = read_notebook(notebook_path)
        total_cells = len(nb.cells)

        # Determine which indices to read
        if cells:
            indices = list(cells)
        elif cell_range:
            indices = parse_range(cell_range, total_cells - 1)
        else:
            click.echo("Error: Provide cell indices or --range", err=True)
            sys.exit(1)

        output_data = []
        for idx in indices:
            if idx < 0 or idx >= total_cells:
                click.echo(f"Warning: Cell {idx} out of range (0-{total_cells-1})", err=True)
                continue

            cell = nb.cells[idx]

            # Only code cells have outputs
            if cell.cell_type != "code":
                continue

            cell_outputs = cell.get("outputs", [])
            if cell_outputs:
                output_data.append({
                    "index": idx,
                    "outputs": cell_outputs,
                })

        if as_json:
            click.echo(json_module.dumps(output_data, indent=2))
        else:
            if not output_data:
                click.echo("No outputs found")
                return

            for cell_data in output_data:
                click.echo(f"=== Cell {cell_data['index']} output ===")
                for output in cell_data["outputs"]:
                    formatted = format_cell_output(output)
                    click.echo(formatted)
                click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command("install-skill")
@click.option("--global", "scope_global", is_flag=True, help="Install globally (~/.claude/skills/)")
@click.option("--local", "scope_local", is_flag=True, help="Install locally (./.claude/skills/)")
def install_skill(scope_global: bool, scope_local: bool):
    """Install the jupyter-cli skill for Claude Code.

    This teaches Claude Code how to use jupyter-cli effectively.

    Examples:
        jupyter-cli install-skill --global   # Available in all projects
        jupyter-cli install-skill --local    # Current directory only
    """
    from importlib.resources import files

    # Determine scope
    if scope_global and scope_local:
        click.echo("Error: Cannot use both --global and --local", err=True)
        sys.exit(1)

    if not scope_global and not scope_local:
        # Interactive prompt
        click.echo("Where would you like to install the jupyter-cli skill?")
        click.echo()
        click.echo("  [1] Global  (~/.claude/skills/) - Available in all projects")
        click.echo("  [2] Local   (./.claude/skills/) - Current directory only")
        click.echo()
        choice = click.prompt("Choose", type=click.Choice(["1", "2"]), default="1")
        scope_global = (choice == "1")
        scope_local = (choice == "2")

    skill_name = "jupyter-cli"

    if scope_global:
        dest_dir = Path.home() / ".claude" / "skills" / skill_name
    else:
        dest_dir = Path(".claude") / "skills" / skill_name

    # Get the source skill file from package data
    try:
        skill_package = files("jupyter_cli.skill")
        source_content = (skill_package / "SKILL.md").read_text()
    except Exception as e:
        click.echo(f"Error: Could not find skill file in package: {e}", err=True)
        sys.exit(1)

    # Create destination directory
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Write the skill file
    dest_file = dest_dir / "SKILL.md"
    dest_file.write_text(source_content)

    click.echo(f"Installed {skill_name} skill to: {dest_dir}")
    click.echo()
    click.echo("The skill will be available after restarting Claude Code.")
    click.echo()
    click.echo("Usage:")
    click.echo("  - Claude will automatically use this skill when working with Jupyter notebooks")
    click.echo("  - Or invoke manually with: /jupyter-cli")


if __name__ == "__main__":
    main()
