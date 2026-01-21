"""Kernel daemon management for persistent Jupyter kernels."""

import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from jupyter_client import KernelManager


# Directory to store kernel state
STATE_DIR = Path.home() / ".jupyter-cli"
KERNELS_DIR = STATE_DIR / "kernels"


def ensure_state_dirs():
    """Ensure state directories exist."""
    STATE_DIR.mkdir(exist_ok=True)
    KERNELS_DIR.mkdir(exist_ok=True)


def get_kernel_info_path(notebook_path: str) -> Path:
    """Get path to kernel info file for a notebook."""
    # Use absolute path hash to handle different notebooks with same name
    abs_path = Path(notebook_path).resolve()
    # Create a safe filename from the notebook path
    safe_name = str(abs_path).replace("/", "_").replace("\\", "_")
    return KERNELS_DIR / f"{safe_name}.json"


def get_kernel_error_path(notebook_path: str) -> Path:
    """Get path to kernel error file for a notebook."""
    abs_path = Path(notebook_path).resolve()
    safe_name = str(abs_path).replace("/", "_").replace("\\", "_")
    return KERNELS_DIR / f"{safe_name}.error"


def save_kernel_error(notebook_path: str, error: str):
    """Save kernel startup error to file."""
    ensure_state_dirs()
    error_path = get_kernel_error_path(notebook_path)
    error_path.write_text(error)


def load_kernel_error(notebook_path: str) -> Optional[str]:
    """Load kernel startup error if exists."""
    error_path = get_kernel_error_path(notebook_path)
    if error_path.exists():
        error = error_path.read_text()
        error_path.unlink()  # Clean up after reading
        return error
    return None


def save_kernel_info(notebook_path: str, kernel_id: str, connection_file: str, pid: int):
    """Save kernel info to state file."""
    ensure_state_dirs()
    info = {
        "notebook_path": str(Path(notebook_path).resolve()),
        "kernel_id": kernel_id,
        "connection_file": connection_file,
        "pid": pid,
        "started_at": time.time(),
    }
    info_path = get_kernel_info_path(notebook_path)
    with open(info_path, "w") as f:
        json.dump(info, f, indent=2)


def load_kernel_info(notebook_path: str) -> Optional[Dict[str, Any]]:
    """Load kernel info from state file."""
    info_path = get_kernel_info_path(notebook_path)
    if not info_path.exists():
        return None
    with open(info_path) as f:
        return json.load(f)


def remove_kernel_info(notebook_path: str):
    """Remove kernel info file."""
    info_path = get_kernel_info_path(notebook_path)
    if info_path.exists():
        info_path.unlink()


def is_kernel_alive(info: Dict[str, Any]) -> bool:
    """Check if a kernel process is still running."""
    pid = info.get("pid")
    if not pid:
        return False
    try:
        # Send signal 0 to check if process exists
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def list_all_kernels() -> list[Dict[str, Any]]:
    """List all known kernels and their status."""
    ensure_state_dirs()
    kernels = []
    for info_file in KERNELS_DIR.glob("*.json"):
        try:
            with open(info_file) as f:
                info = json.load(f)
                info["alive"] = is_kernel_alive(info)
                kernels.append(info)
        except (json.JSONDecodeError, IOError):
            continue
    return kernels


def start_kernel_daemon(notebook_path: str, kernel_name: str = "python3") -> Dict[str, Any]:
    """
    Start a kernel daemon process.

    This function forks a daemon process that keeps the kernel alive.
    The parent process returns immediately with kernel info.
    """
    ensure_state_dirs()

    # Check if kernel already exists for this notebook
    existing = load_kernel_info(notebook_path)
    if existing and is_kernel_alive(existing):
        return {
            "status": "already_running",
            "kernel_id": existing["kernel_id"],
            "pid": existing["pid"],
            "connection_file": existing["connection_file"],
        }

    # Clean up stale info if exists
    if existing:
        remove_kernel_info(notebook_path)

    # Fork to create daemon
    pid = os.fork()

    if pid > 0:
        # Parent process - wait briefly for kernel to start, then return
        time.sleep(1.5)  # Give daemon time to start kernel
        info = load_kernel_info(notebook_path)
        if info:
            return {
                "status": "started",
                "kernel_id": info["kernel_id"],
                "pid": info["pid"],
                "connection_file": info["connection_file"],
            }
        else:
            # Check for error message from daemon
            error = load_kernel_error(notebook_path)
            if error:
                return {"status": "error", "message": error}
            return {"status": "error", "message": "Kernel failed to start (unknown error)"}

    else:
        # Child process - become daemon
        try:
            # Create new session
            os.setsid()

            # Fork again to prevent zombie processes
            pid2 = os.fork()
            if pid2 > 0:
                os._exit(0)

            # Now we're the daemon process
            daemon_pid = os.getpid()

            # Redirect standard file descriptors
            sys.stdin.close()

            # Start the kernel
            km = KernelManager(kernel_name=kernel_name)
            km.start_kernel()

            kernel_id = km.kernel_id or f"kernel-{daemon_pid}"
            connection_file = km.connection_file

            # Save kernel info
            save_kernel_info(notebook_path, kernel_id, connection_file, daemon_pid)

            # Set up signal handlers for clean shutdown
            def shutdown_handler(signum, frame):
                km.shutdown_kernel(now=True)
                remove_kernel_info(notebook_path)
                os._exit(0)

            signal.signal(signal.SIGTERM, shutdown_handler)
            signal.signal(signal.SIGINT, shutdown_handler)

            # Keep daemon alive
            while True:
                if not km.is_alive():
                    remove_kernel_info(notebook_path)
                    os._exit(1)
                time.sleep(5)

        except Exception as e:
            # Save error for parent process to read
            error_msg = str(e)
            # Add helpful hints for common errors
            if "No such file or directory" in error_msg and "kernel" in error_msg.lower():
                error_msg = f"{error_msg}\nHint: Make sure ipykernel is installed: pip install ipykernel"
            elif "No kernel" in error_msg or "not found" in error_msg.lower():
                error_msg = f"{error_msg}\nHint: Install a kernel with: pip install ipykernel"

            try:
                save_kernel_error(notebook_path, error_msg)
                with open(STATE_DIR / "daemon_error.log", "a") as f:
                    f.write(f"{time.time()}: {e}\n")
            except:
                pass
            os._exit(1)


def stop_kernel(notebook_path: str) -> Dict[str, Any]:
    """Stop a running kernel for a notebook."""
    info = load_kernel_info(notebook_path)
    if not info:
        return {"status": "not_found", "message": "No kernel found for this notebook"}

    if not is_kernel_alive(info):
        remove_kernel_info(notebook_path)
        return {"status": "not_running", "message": "Kernel was not running (cleaned up stale info)"}

    pid = info["pid"]
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait for process to terminate
        for _ in range(10):
            time.sleep(0.2)
            if not is_kernel_alive(info):
                break
        remove_kernel_info(notebook_path)
        return {"status": "stopped", "kernel_id": info["kernel_id"], "pid": pid}
    except (OSError, ProcessLookupError) as e:
        remove_kernel_info(notebook_path)
        return {"status": "error", "message": str(e)}


def stop_all_kernels() -> Dict[str, Any]:
    """Stop all running kernels."""
    results = []
    for info in list_all_kernels():
        if info.get("alive"):
            result = stop_kernel(info["notebook_path"])
            results.append({
                "notebook": info["notebook_path"],
                "result": result,
            })
    return {"stopped": len(results), "results": results}
