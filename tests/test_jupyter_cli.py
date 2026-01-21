"""Comprehensive test suite for jupyter-cli."""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from jupyter_cli.notebook import (
    read_notebook,
    get_cell_source,
    get_cell_type,
    get_cell_count,
    get_code_cells,
    validate_cell_indices,
)
from jupyter_cli.daemon import (
    start_kernel_daemon,
    stop_kernel,
    stop_all_kernels,
    load_kernel_info,
    is_kernel_alive,
    list_all_kernels,
)
from jupyter_cli.client import (
    connect_to_kernel,
    execute_cells,
    execute_code,
    KernelNotRunningError,
)


TEST_DIR = Path(__file__).parent
TEST_NOTEBOOK = TEST_DIR / "test_notebook.ipynb"
TEST_NOTEBOOK_WITH_OUTPUTS = TEST_DIR / "test_notebook_with_outputs.ipynb"


def run_cli(*args) -> subprocess.CompletedProcess:
    """Run jupyter-cli command and return result."""
    cmd = ["jupyter-cli"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


# =============================================================================
# Notebook Parsing Tests
# =============================================================================

class TestNotebookParsing:
    """Tests for notebook parsing utilities."""

    def test_read_notebook(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        assert nb is not None
        assert len(nb.cells) == 6

    def test_read_notebook_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_notebook("/nonexistent/path.ipynb")

    def test_read_notebook_invalid_extension(self):
        with pytest.raises(ValueError, match="Not a notebook"):
            read_notebook(__file__)  # This .py file

    def test_get_cell_count(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        assert get_cell_count(nb) == 6

    def test_get_code_cells(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        code_cells = get_code_cells(nb)
        assert code_cells == [0, 1, 2, 4, 5]  # Cell 3 is markdown

    def test_get_cell_source(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        source = get_cell_source(nb, 0)
        assert "x = 10" in source

    def test_get_cell_source_out_of_range(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        with pytest.raises(IndexError, match="out of range"):
            get_cell_source(nb, 100)

    def test_get_cell_type(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        assert get_cell_type(nb, 0) == "code"
        assert get_cell_type(nb, 3) == "markdown"

    def test_validate_cell_indices_valid(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        error = validate_cell_indices(nb, [0, 1, 2])
        assert error is None

    def test_validate_cell_indices_invalid(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        error = validate_cell_indices(nb, [0, 100])
        assert error is not None
        assert "out of range" in error


# =============================================================================
# Kernel Lifecycle Tests
# =============================================================================

class TestKernelLifecycle:
    """Tests for kernel start/stop/status."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Ensure kernel is stopped after each test."""
        yield
        try:
            stop_kernel(str(TEST_NOTEBOOK))
        except Exception:
            pass

    def test_start_kernel(self):
        result = start_kernel_daemon(str(TEST_NOTEBOOK))
        assert result["status"] in ("started", "already_running")
        assert "kernel_id" in result
        assert "pid" in result

    def test_kernel_info_saved(self):
        start_kernel_daemon(str(TEST_NOTEBOOK))
        info = load_kernel_info(str(TEST_NOTEBOOK))
        assert info is not None
        assert "kernel_id" in info
        assert "pid" in info
        assert "connection_file" in info

    def test_is_kernel_alive(self):
        start_kernel_daemon(str(TEST_NOTEBOOK))
        info = load_kernel_info(str(TEST_NOTEBOOK))
        assert is_kernel_alive(info) is True

    def test_stop_kernel(self):
        start_kernel_daemon(str(TEST_NOTEBOOK))
        result = stop_kernel(str(TEST_NOTEBOOK))
        assert result["status"] == "stopped"

    def test_stop_kernel_not_found(self):
        result = stop_kernel("/nonexistent/notebook.ipynb")
        assert result["status"] == "not_found"

    def test_kernel_already_running(self):
        result1 = start_kernel_daemon(str(TEST_NOTEBOOK))
        assert result1["status"] == "started"

        result2 = start_kernel_daemon(str(TEST_NOTEBOOK))
        assert result2["status"] == "already_running"
        assert result2["kernel_id"] == result1["kernel_id"]

    def test_list_all_kernels(self):
        start_kernel_daemon(str(TEST_NOTEBOOK))
        kernels = list_all_kernels()
        assert len(kernels) >= 1
        assert any(k["notebook_path"] == str(TEST_NOTEBOOK.resolve()) for k in kernels)

    def test_stop_all_kernels(self):
        start_kernel_daemon(str(TEST_NOTEBOOK))
        result = stop_all_kernels()
        assert result["stopped"] >= 1


# =============================================================================
# Cell Execution Tests
# =============================================================================

class TestCellExecution:
    """Tests for cell execution."""

    @pytest.fixture(autouse=True)
    def setup_kernel(self):
        """Start kernel before tests, stop after."""
        start_kernel_daemon(str(TEST_NOTEBOOK))
        time.sleep(1)
        yield
        stop_kernel(str(TEST_NOTEBOOK))

    def test_execute_single_cell(self):
        results = execute_cells(str(TEST_NOTEBOOK), [0], verbose=False)
        assert len(results) == 1
        assert results[0]["status"] == "ok"
        assert results[0]["cell_index"] == 0

    def test_execute_multiple_cells(self):
        results = execute_cells(str(TEST_NOTEBOOK), [0, 1, 2], verbose=False)
        assert len(results) == 3
        assert all(r["status"] == "ok" for r in results)

    def test_state_persistence_within_call(self):
        # Execute cells 0 and 1 together
        results = execute_cells(str(TEST_NOTEBOOK), [0, 1], verbose=False)
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "ok"

        # Cell 1 uses x from cell 0
        outputs = results[1]["outputs"]
        output_text = "".join(o.get("text", "") for o in outputs if o.get("type") == "stream")
        assert "20" in output_text

    def test_state_persistence_across_calls(self):
        # Execute cell 0 in first call
        results1 = execute_cells(str(TEST_NOTEBOOK), [0], verbose=False)
        assert results1[0]["status"] == "ok"

        # Execute cell 1 in separate call - should still have x
        results2 = execute_cells(str(TEST_NOTEBOOK), [1], verbose=False)
        assert results2[0]["status"] == "ok"

        outputs = results2[0]["outputs"]
        output_text = "".join(o.get("text", "") for o in outputs if o.get("type") == "stream")
        assert "20" in output_text

    def test_skip_markdown_cell(self):
        results = execute_cells(str(TEST_NOTEBOOK), [3], verbose=False)
        assert len(results) == 1
        assert results[0]["status"] == "skipped"
        assert results[0]["cell_type"] == "markdown"

    def test_execute_with_timeout(self):
        results = execute_cells(str(TEST_NOTEBOOK), [0], timeout=10, verbose=False)
        assert results[0]["status"] == "ok"

    def test_connect_to_kernel(self):
        kc = connect_to_kernel(str(TEST_NOTEBOOK))
        assert kc is not None
        kc.stop_channels()

    def test_execute_code_directly(self):
        kc = connect_to_kernel(str(TEST_NOTEBOOK))
        try:
            result = execute_code(kc, "1 + 1")
            assert result["status"] == "ok"
        finally:
            kc.stop_channels()


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_connect_without_kernel(self):
        stop_kernel(str(TEST_NOTEBOOK))
        with pytest.raises(KernelNotRunningError):
            connect_to_kernel(str(TEST_NOTEBOOK))

    def test_execute_without_kernel(self):
        stop_kernel(str(TEST_NOTEBOOK))
        with pytest.raises(KernelNotRunningError):
            execute_cells(str(TEST_NOTEBOOK), [0], verbose=False)

    def test_invalid_cell_index(self):
        start_kernel_daemon(str(TEST_NOTEBOOK))
        time.sleep(1)
        try:
            with pytest.raises(ValueError, match="out of range"):
                execute_cells(str(TEST_NOTEBOOK), [100], verbose=False)
        finally:
            stop_kernel(str(TEST_NOTEBOOK))

    def test_negative_cell_index(self):
        start_kernel_daemon(str(TEST_NOTEBOOK))
        time.sleep(1)
        try:
            with pytest.raises(ValueError, match="out of range"):
                execute_cells(str(TEST_NOTEBOOK), [-1], verbose=False)
        finally:
            stop_kernel(str(TEST_NOTEBOOK))


# =============================================================================
# CLI Command Tests
# =============================================================================

class TestCLIStart:
    """Tests for 'jupyter-cli start' command."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        run_cli("stop", str(TEST_NOTEBOOK))

    def test_start_command(self):
        result = run_cli("start", str(TEST_NOTEBOOK))
        assert result.returncode == 0
        assert "Kernel started" in result.stdout or "already running" in result.stdout

    def test_start_shows_cell_count(self):
        result = run_cli("start", str(TEST_NOTEBOOK))
        assert "6 cells" in result.stdout


class TestCLIStatus:
    """Tests for 'jupyter-cli status' command."""

    def test_status_no_kernels(self):
        run_cli("stop", "--all")
        result = run_cli("status")
        assert "No kernels found" in result.stdout

    def test_status_with_kernel(self):
        run_cli("start", str(TEST_NOTEBOOK))
        result = run_cli("status", str(TEST_NOTEBOOK))
        assert "running" in result.stdout
        run_cli("stop", str(TEST_NOTEBOOK))

    def test_status_all_kernels(self):
        run_cli("start", str(TEST_NOTEBOOK))
        result = run_cli("status")
        assert "kernel(s)" in result.stdout or "running" in result.stdout
        run_cli("stop", str(TEST_NOTEBOOK))


class TestCLIStop:
    """Tests for 'jupyter-cli stop' command."""

    def test_stop_command(self):
        run_cli("start", str(TEST_NOTEBOOK))
        result = run_cli("stop", str(TEST_NOTEBOOK))
        assert result.returncode == 0
        assert "stopped" in result.stdout.lower()

    def test_stop_not_found(self):
        run_cli("stop", str(TEST_NOTEBOOK))  # Ensure stopped
        result = run_cli("stop", str(TEST_NOTEBOOK))
        assert "No kernel found" in result.stdout or "not running" in result.stdout.lower()

    def test_stop_all(self):
        run_cli("start", str(TEST_NOTEBOOK))
        result = run_cli("stop", "--all")
        assert result.returncode == 0


class TestCLIExec:
    """Tests for 'jupyter-cli exec' command."""

    @pytest.fixture(autouse=True)
    def setup_kernel(self):
        run_cli("start", str(TEST_NOTEBOOK))
        time.sleep(1)
        yield
        run_cli("stop", str(TEST_NOTEBOOK))

    def test_exec_single_cell(self):
        result = run_cli("exec", str(TEST_NOTEBOOK), "0")
        assert result.returncode == 0
        assert "Set x = 10" in result.stdout

    def test_exec_multiple_cells(self):
        result = run_cli("exec", str(TEST_NOTEBOOK), "0", "1", "2")
        assert result.returncode == 0
        assert "Set x = 10" in result.stdout
        assert "Set y" in result.stdout

    def test_exec_quiet_mode(self):
        result = run_cli("exec", str(TEST_NOTEBOOK), "0", "--quiet")
        assert result.returncode == 0
        assert "Set x" not in result.stdout

    def test_exec_without_kernel(self):
        run_cli("stop", str(TEST_NOTEBOOK))
        result = run_cli("exec", str(TEST_NOTEBOOK), "0")
        assert result.returncode != 0
        assert "No kernel found" in result.stderr or "start" in result.stderr.lower()


class TestCLIList:
    """Tests for 'jupyter-cli list' command."""

    def test_list_all_cells(self):
        result = run_cli("list", str(TEST_NOTEBOOK))
        assert result.returncode == 0
        assert "[0] code:" in result.stdout
        assert "[3] markdown:" in result.stdout

    def test_list_code_only(self):
        result = run_cli("list", str(TEST_NOTEBOOK), "--code")
        assert result.returncode == 0
        assert "[0] code:" in result.stdout
        assert "markdown:" not in result.stdout

    def test_list_markdown_only(self):
        result = run_cli("list", str(TEST_NOTEBOOK), "--markdown")
        assert result.returncode == 0
        assert "[3] markdown:" in result.stdout
        assert "code:" not in result.stdout

    def test_list_with_range(self):
        result = run_cli("list", str(TEST_NOTEBOOK), "--range", "0-2")
        assert result.returncode == 0
        assert "[0]" in result.stdout
        assert "[1]" in result.stdout
        assert "[2]" in result.stdout
        assert "[3]" not in result.stdout

    def test_list_with_open_range(self):
        result = run_cli("list", str(TEST_NOTEBOOK), "--range", "4-")
        assert result.returncode == 0
        assert "[4]" in result.stdout
        assert "[5]" in result.stdout
        assert "[3]" not in result.stdout


class TestCLIRead:
    """Tests for 'jupyter-cli read' command."""

    def test_read_specific_cells(self):
        result = run_cli("read", str(TEST_NOTEBOOK), "0", "1")
        assert result.returncode == 0
        assert "=== Cell 0 (code) ===" in result.stdout
        assert "x = 10" in result.stdout
        assert "=== Cell 1 (code) ===" in result.stdout

    def test_read_code_only(self):
        result = run_cli("read", str(TEST_NOTEBOOK), "--code")
        assert result.returncode == 0
        assert "=== Cell 0 (code) ===" in result.stdout
        assert "(markdown)" not in result.stdout

    def test_read_markdown_only(self):
        result = run_cli("read", str(TEST_NOTEBOOK), "--markdown")
        assert result.returncode == 0
        assert "=== Cell 3 (markdown) ===" in result.stdout

    def test_read_with_range(self):
        result = run_cli("read", str(TEST_NOTEBOOK), "--range", "0-1")
        assert result.returncode == 0
        assert "=== Cell 0" in result.stdout
        assert "=== Cell 1" in result.stdout
        assert "=== Cell 2" not in result.stdout

    def test_read_combined_filters(self):
        result = run_cli("read", str(TEST_NOTEBOOK), "--code", "--range", "0-3")
        assert result.returncode == 0
        assert "=== Cell 0 (code) ===" in result.stdout
        assert "=== Cell 3" not in result.stdout  # markdown filtered out

    def test_read_json_output(self):
        result = run_cli("read", str(TEST_NOTEBOOK), "0", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["index"] == 0
        assert data[0]["type"] == "code"

    def test_read_no_args_error(self):
        result = run_cli("read", str(TEST_NOTEBOOK))
        assert result.returncode != 0
        assert "Provide cell indices" in result.stderr


class TestCLISearch:
    """Tests for 'jupyter-cli search' command."""

    def test_search_basic(self):
        result = run_cli("search", str(TEST_NOTEBOOK), "print")
        assert result.returncode == 0
        assert "match" in result.stdout.lower()
        assert "[0]" in result.stdout

    def test_search_no_match(self):
        result = run_cli("search", str(TEST_NOTEBOOK), "nonexistent_pattern_xyz")
        assert result.returncode == 0
        assert "No matches found" in result.stdout

    def test_search_regex(self):
        result = run_cli("search", str(TEST_NOTEBOOK), "x.*=", "--regex")
        assert result.returncode == 0
        assert "match" in result.stdout.lower()

    def test_search_code_only(self):
        result = run_cli("search", str(TEST_NOTEBOOK), "skipped", "--code")
        assert result.returncode == 0
        assert "No matches found" in result.stdout  # "skipped" is in markdown

    def test_search_markdown_only(self):
        result = run_cli("search", str(TEST_NOTEBOOK), "skipped", "--markdown")
        assert result.returncode == 0
        assert "[3] markdown:" in result.stdout

    def test_search_with_context(self):
        result = run_cli("search", str(TEST_NOTEBOOK), "result", "--context", "1")
        assert result.returncode == 0
        assert ">" in result.stdout  # Context marker

    def test_search_invalid_regex(self):
        result = run_cli("search", str(TEST_NOTEBOOK), "[invalid", "--regex")
        assert result.returncode != 0
        assert "Invalid regex" in result.stderr


class TestCLIOutputs:
    """Tests for 'jupyter-cli outputs' command."""

    def test_outputs_with_data(self):
        result = run_cli("outputs", str(TEST_NOTEBOOK_WITH_OUTPUTS), "0", "1")
        assert result.returncode == 0
        assert "=== Cell 0 output ===" in result.stdout
        assert "[stdout]" in result.stdout

    def test_outputs_execute_result(self):
        result = run_cli("outputs", str(TEST_NOTEBOOK_WITH_OUTPUTS), "2")
        assert result.returncode == 0
        assert "[result]" in result.stdout
        assert "42" in result.stdout

    def test_outputs_error(self):
        result = run_cli("outputs", str(TEST_NOTEBOOK_WITH_OUTPUTS), "3")
        assert result.returncode == 0
        assert "[error]" in result.stdout
        assert "NameError" in result.stdout

    def test_outputs_with_range(self):
        result = run_cli("outputs", str(TEST_NOTEBOOK_WITH_OUTPUTS), "--range", "0-2")
        assert result.returncode == 0
        assert "=== Cell 0 output ===" in result.stdout
        assert "=== Cell 1 output ===" in result.stdout

    def test_outputs_json(self):
        result = run_cli("outputs", str(TEST_NOTEBOOK_WITH_OUTPUTS), "0", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["index"] == 0
        assert "outputs" in data[0]

    def test_outputs_no_outputs(self):
        result = run_cli("outputs", str(TEST_NOTEBOOK), "0")
        assert result.returncode == 0
        assert "No outputs found" in result.stdout


class TestCLIInfo:
    """Tests for 'jupyter-cli info' command."""

    def test_info_command(self):
        result = run_cli("info", str(TEST_NOTEBOOK))
        assert result.returncode == 0
        assert "Total cells: 6" in result.stdout
        assert "Code cells: 5" in result.stdout


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegrationWorkflow:
    """Integration tests for complete workflows."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        run_cli("stop", str(TEST_NOTEBOOK))

    def test_full_workflow(self):
        """Test complete workflow: start -> exec setup -> exec experiment -> stop."""
        # Start kernel
        result = run_cli("start", str(TEST_NOTEBOOK))
        assert result.returncode == 0

        time.sleep(1)

        # Execute setup cells (0, 1, 2, 4)
        result = run_cli("exec", str(TEST_NOTEBOOK), "0", "1", "2", "4")
        assert result.returncode == 0
        assert "Set x = 10" in result.stdout
        assert "z = x + y = 30" in result.stdout

        # Execute experiment cell
        result = run_cli("exec", str(TEST_NOTEBOOK), "5")
        assert result.returncode == 0
        assert "result = x + y + z = 60" in result.stdout

        # Re-execute experiment (state should persist)
        result = run_cli("exec", str(TEST_NOTEBOOK), "5")
        assert result.returncode == 0
        assert "result = x + y + z = 60" in result.stdout

        # Stop kernel
        result = run_cli("stop", str(TEST_NOTEBOOK))
        assert result.returncode == 0

    def test_explore_workflow(self):
        """Test exploration workflow: list -> search -> read."""
        # List cells
        result = run_cli("list", str(TEST_NOTEBOOK))
        assert result.returncode == 0
        assert "[0] code:" in result.stdout

        # Search for specific functionality
        result = run_cli("search", str(TEST_NOTEBOOK), "result")
        assert result.returncode == 0
        assert "[5]" in result.stdout

        # Read the found cell
        result = run_cli("read", str(TEST_NOTEBOOK), "5")
        assert result.returncode == 0
        assert "result = x + y + z" in result.stdout
