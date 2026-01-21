"""Basic tests for jupyter-cli."""

import os
import time
from pathlib import Path

import pytest

from jupyter_cli.notebook import read_notebook, get_cell_source, get_cell_count, get_code_cells
from jupyter_cli.daemon import start_kernel_daemon, stop_kernel, load_kernel_info, is_kernel_alive
from jupyter_cli.client import connect_to_kernel, execute_cells, KernelNotRunningError


TEST_NOTEBOOK = Path(__file__).parent / "test_notebook.ipynb"


class TestNotebookParsing:
    def test_read_notebook(self):
        nb = read_notebook(str(TEST_NOTEBOOK))
        assert nb is not None
        assert len(nb.cells) == 6

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


class TestKernelLifecycle:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Ensure kernel is stopped after each test."""
        yield
        try:
            stop_kernel(str(TEST_NOTEBOOK))
        except Exception:
            pass

    def test_start_and_stop_kernel(self):
        result = start_kernel_daemon(str(TEST_NOTEBOOK))
        assert result["status"] in ("started", "already_running")
        assert "kernel_id" in result
        assert "pid" in result

        # Verify kernel info exists
        info = load_kernel_info(str(TEST_NOTEBOOK))
        assert info is not None
        assert is_kernel_alive(info)

        # Stop kernel
        stop_result = stop_kernel(str(TEST_NOTEBOOK))
        assert stop_result["status"] == "stopped"

    def test_kernel_already_running(self):
        # Start first time
        result1 = start_kernel_daemon(str(TEST_NOTEBOOK))
        assert result1["status"] == "started"

        # Try to start again
        result2 = start_kernel_daemon(str(TEST_NOTEBOOK))
        assert result2["status"] == "already_running"
        assert result2["kernel_id"] == result1["kernel_id"]


class TestCellExecution:
    @pytest.fixture(autouse=True)
    def setup_kernel(self):
        """Start kernel before tests, stop after."""
        start_kernel_daemon(str(TEST_NOTEBOOK))
        time.sleep(1)  # Give kernel time to be ready
        yield
        stop_kernel(str(TEST_NOTEBOOK))

    def test_execute_single_cell(self):
        results = execute_cells(str(TEST_NOTEBOOK), [0], verbose=False)
        assert len(results) == 1
        assert results[0]["status"] == "ok"

    def test_execute_multiple_cells(self):
        results = execute_cells(str(TEST_NOTEBOOK), [0, 1, 2], verbose=False)
        assert len(results) == 3
        assert all(r["status"] == "ok" for r in results)

    def test_state_persistence(self):
        # Execute cell 0 which sets x = 10
        results1 = execute_cells(str(TEST_NOTEBOOK), [0], verbose=False)
        assert results1[0]["status"] == "ok"

        # Execute cell 1 which uses x
        results2 = execute_cells(str(TEST_NOTEBOOK), [1], verbose=False)
        assert results2[0]["status"] == "ok"

        # Verify output shows y = 20
        outputs = results2[0]["outputs"]
        output_text = "".join(o.get("text", "") for o in outputs if o.get("type") == "stream")
        assert "20" in output_text

    def test_skip_markdown_cell(self):
        results = execute_cells(str(TEST_NOTEBOOK), [3], verbose=False)
        assert len(results) == 1
        assert results[0]["status"] == "skipped"
        assert results[0]["cell_type"] == "markdown"


class TestErrorHandling:
    def test_connect_without_kernel(self):
        # Ensure no kernel is running
        stop_kernel(str(TEST_NOTEBOOK))

        with pytest.raises(KernelNotRunningError):
            connect_to_kernel(str(TEST_NOTEBOOK))

    def test_invalid_cell_index(self):
        start_kernel_daemon(str(TEST_NOTEBOOK))
        time.sleep(1)

        try:
            with pytest.raises(ValueError, match="out of range"):
                execute_cells(str(TEST_NOTEBOOK), [100], verbose=False)
        finally:
            stop_kernel(str(TEST_NOTEBOOK))
