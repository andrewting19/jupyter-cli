"""Client for executing cells on a persistent kernel."""

import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

from jupyter_client import BlockingKernelClient

from .daemon import load_kernel_info, is_kernel_alive
from .notebook import read_notebook, get_cell_source, get_cell_type, validate_cell_indices


class ExecutionError(Exception):
    """Error during cell execution."""
    pass


class KernelNotRunningError(Exception):
    """Kernel is not running."""
    pass


def connect_to_kernel(notebook_path: str) -> BlockingKernelClient:
    """Connect to an existing kernel for a notebook."""
    info = load_kernel_info(notebook_path)
    if not info:
        raise KernelNotRunningError(f"No kernel found for notebook: {notebook_path}")

    if not is_kernel_alive(info):
        raise KernelNotRunningError(f"Kernel is not running (pid {info.get('pid')} not found)")

    connection_file = info["connection_file"]
    if not Path(connection_file).exists():
        raise KernelNotRunningError(f"Connection file not found: {connection_file}")

    kc = BlockingKernelClient(connection_file=connection_file)
    kc.load_connection_file()
    kc.start_channels()

    # Wait for kernel to be ready
    try:
        kc.wait_for_ready(timeout=10)
    except Exception as e:
        kc.stop_channels()
        raise KernelNotRunningError(f"Kernel not responding: {e}")

    return kc


def execute_code(kc: BlockingKernelClient, code: str, timeout: float = 600) -> Dict[str, Any]:
    """
    Execute code on the kernel and capture all outputs.

    Returns a dict with:
    - status: 'ok' or 'error'
    - outputs: list of output dicts
    - error: error info if status is 'error'
    """
    outputs = []
    error_info = None

    # Execute the code
    msg_id = kc.execute(code)

    # Collect outputs from IOPub channel
    while True:
        try:
            msg = kc.get_iopub_msg(timeout=timeout)
        except Exception:
            break

        msg_type = msg["header"]["msg_type"]
        content = msg["content"]

        # Check if this message is for our execution
        if msg.get("parent_header", {}).get("msg_id") != msg_id:
            continue

        if msg_type == "stream":
            outputs.append({
                "type": "stream",
                "name": content.get("name", "stdout"),
                "text": content.get("text", ""),
            })

        elif msg_type == "execute_result":
            outputs.append({
                "type": "execute_result",
                "data": content.get("data", {}),
                "execution_count": content.get("execution_count"),
            })

        elif msg_type == "display_data":
            outputs.append({
                "type": "display_data",
                "data": content.get("data", {}),
            })

        elif msg_type == "error":
            error_info = {
                "ename": content.get("ename", "Error"),
                "evalue": content.get("evalue", ""),
                "traceback": content.get("traceback", []),
            }
            outputs.append({
                "type": "error",
                **error_info,
            })

        elif msg_type == "status":
            if content.get("execution_state") == "idle":
                break

    # Get reply to check execution status
    try:
        reply = kc.get_shell_msg(timeout=timeout)
        reply_status = reply["content"].get("status", "ok")
    except Exception:
        reply_status = "ok"  # Assume ok if we can't get reply

    return {
        "status": "error" if error_info else reply_status,
        "outputs": outputs,
        "error": error_info,
    }


def format_output(output: Dict[str, Any]) -> str:
    """Format a single output for display."""
    output_type = output.get("type")

    if output_type == "stream":
        return output.get("text", "")

    elif output_type == "execute_result":
        data = output.get("data", {})
        # Prefer text/plain, then text/html
        if "text/plain" in data:
            return data["text/plain"]
        elif "text/html" in data:
            return f"[HTML output]\n{data['text/html'][:500]}..."
        else:
            return f"[{', '.join(data.keys())}]"

    elif output_type == "display_data":
        data = output.get("data", {})
        if "text/plain" in data:
            return data["text/plain"]
        elif "image/png" in data:
            return "[Image: PNG]"
        elif "image/jpeg" in data:
            return "[Image: JPEG]"
        else:
            return f"[Display: {', '.join(data.keys())}]"

    elif output_type == "error":
        tb = output.get("traceback", [])
        if tb:
            # Traceback lines may contain ANSI codes
            return "\n".join(tb)
        else:
            return f"{output.get('ename', 'Error')}: {output.get('evalue', '')}"

    return str(output)


def execute_cells(
    notebook_path: str,
    cell_indices: List[int],
    timeout: float = 600,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Execute specific cells from a notebook on the persistent kernel.

    Args:
        notebook_path: Path to the notebook file
        cell_indices: List of cell indices to execute (0-indexed)
        timeout: Timeout per cell in seconds
        verbose: Whether to print output

    Returns:
        List of execution results for each cell
    """
    # Read notebook
    notebook = read_notebook(notebook_path)

    # Validate indices
    error = validate_cell_indices(notebook, cell_indices)
    if error:
        raise ValueError(error)

    # Connect to kernel
    kc = connect_to_kernel(notebook_path)

    results = []
    try:
        for idx in cell_indices:
            cell_type = get_cell_type(notebook, idx)

            # Skip non-code cells
            if cell_type != "code":
                if verbose:
                    print(f"[Cell {idx}] Skipping {cell_type} cell")
                results.append({
                    "cell_index": idx,
                    "cell_type": cell_type,
                    "status": "skipped",
                    "outputs": [],
                })
                continue

            code = get_cell_source(notebook, idx)

            if verbose:
                # Show cell being executed
                code_preview = code[:100] + "..." if len(code) > 100 else code
                code_preview = code_preview.replace("\n", "\\n")
                print(f"[Cell {idx}] Executing: {code_preview}")

            # Execute
            result = execute_code(kc, code, timeout=timeout)
            result["cell_index"] = idx
            result["cell_type"] = cell_type

            # Print outputs
            if verbose and result["outputs"]:
                for output in result["outputs"]:
                    formatted = format_output(output)
                    if formatted:
                        print(formatted, end="" if output.get("type") == "stream" else "\n")

            if verbose and result["status"] == "error":
                print(f"[Cell {idx}] Error!", file=sys.stderr)

            results.append(result)

    finally:
        kc.stop_channels()

    return results
