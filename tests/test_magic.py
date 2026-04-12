"""Test magic commands."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from qonsole.magic import MagicCmds


class TestMagicCmds:
    """Test magic command handlers."""

    @pytest.fixture
    def console(self):
        """Create a mock console."""
        console = Mock()
        # Use a real dict that will be modified by runpy
        locals_dict = {}
        console.interpreter = Mock()
        console.interpreter.locals = locals_dict
        # Ensure command_history and export_as_script exist for export tests
        console.command_history = Mock()
        console.export_as_script = Mock()
        return console

    @pytest.fixture
    def magic(self, console):
        """Create a MagicCmds instance."""
        return MagicCmds(console)

    def test_pwd(self, magic):
        """Test %pwd returns current directory."""
        result = magic._PWD()
        assert os.getcwd() in result

    def test_cd(self, magic):
        """Test %cd changes directory."""
        original = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                magic._CD(tmpdir)
                # Normalize paths (macOS has /private/var and /var symlinks)
                assert os.path.realpath(tmpdir) == os.path.realpath(os.getcwd())
            finally:
                os.chdir(original)  # Restore before tmpdir cleanup

    def test_cd_tilde(self, magic):
        """Test %cd ~ expands to home directory."""
        original = os.getcwd()
        try:
            magic._CD("~")
            assert os.getcwd() == str(Path.home())
        finally:
            os.chdir(original)  # Restore

    def test_ls(self, magic):
        """Test %ls lists directory."""
        result = magic._LS()
        assert isinstance(result, str)
        # Should contain some files/directories
        assert len(result) > 0

    def test_clear(self, magic, console):
        """Test %clear calls console.clear()."""
        result = magic._CLEAR()
        console.clear.assert_called_once()
        assert result == ""

    def test_who(self, magic, console):
        """Test %who lists variables."""
        console.interpreter.locals = {"x": 1, "y": 2}
        result = magic._WHO()
        assert "x" in result
        assert "y" in result

    def test_whos(self, magic, console):
        """Test %whos displays detailed variable info."""
        console.interpreter.locals = {"x": 42, "name": "test", "data": [1, 2, 3]}
        result = magic._WHOS()
        assert "Variable" in result
        assert "Type" in result
        assert "x" in result
        assert "int" in result
        assert "name" in result
        assert "str" in result
        assert "data" in result
        assert "list" in result

    def test_whos_no_variables(self, magic, console):
        """Test %whos with no variables."""
        console.interpreter.locals = {}
        result = magic._WHOS()
        assert "No variables" in result

    def test_whos_excludes_private(self, magic, console):
        """Test %whos excludes private variables."""
        console.interpreter.locals = {"x": 1, "_private": 2, "__dunder__": 3}
        result = magic._WHOS()
        assert "x" in result
        assert "_private" not in result
        assert "__dunder__" not in result

    def test_timeit(self, magic, console):
        """Test %timeit times a statement."""
        result = magic._TIMEIT("1 + 1")
        assert isinstance(result, str)
        assert any(unit in result for unit in ["ns", "µs", "ms", "s"])
        assert "per loop" in result

    def test_timeit_no_args(self, magic):
        """Test %timeit without arguments."""
        result = magic._TIMEIT()
        assert "Usage" in result

    def test_timeit_with_error(self, magic):
        """Test %timeit with invalid code."""
        result = magic._TIMEIT("invalid syntax here!")
        assert "Error" in result

    def test_run_no_args(self, magic):
        """Test %run without arguments."""
        result = magic._RUN(None)
        assert "Usage" in result

    def test_run_file_not_found(self, magic):
        """Test %run with non-existent file."""
        result = magic._RUN("/nonexistent/path/to/script.py")
        assert "File not found" in result

    def test_run_script(self, magic, console):
        """Test %run executes a script file."""
        # Create a temporary script file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as script:
            script.write("test_var = 'from_script'\n")
            script_path = script.name

        try:
            result = magic._RUN(script_path)
            # Empty result means success
            assert result == ""
        finally:
            os.unlink(script_path)

    def test_run_script_with_tilde(self, magic, console):
        """Test %run with ~ expansion."""
        # Create a script in home directory
        home = Path.home()
        script_path = home / "test_qonsole_script.py"

        try:
            script_path.write_text("tilde_test = True\n")
            result = magic._RUN(f"~/{script_path.name}")
            # Empty result means success
            assert result == ""
        finally:
            if script_path.exists():
                script_path.unlink()

    def test_run_script_with_error(self, magic):
        """Test %run with a script that has errors."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as script:
            script.write("raise ValueError('test error')\n")
            script_path = script.name

        try:
            result = magic._RUN(script_path)
            assert "Error running script" in result
            assert "ValueError" in result or "test error" in result
        finally:
            os.unlink(script_path)

    def test_help_no_args(self, magic):
        """Test %help lists magic commands."""
        result = magic._HELP()
        assert "Available magic commands" in result
        assert "%pwd" in result
        assert "%cd" in result
        assert "%ls" in result
        assert "%who" in result
        assert "%whos" in result
        assert "%timeit" in result
        assert "%run" in result
        assert "%clear" in result
        assert "%help" in result
        assert "%export" in result

    def test_help_with_builtin(self, magic, console):
        """Test %help with a built-in object."""
        console.interpreter.locals = {"test_list": [1, 2, 3]}
        result = magic._HELP("test_list")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_help_with_invalid_object(self, magic, console):
        """Test %help with invalid object name."""
        result = magic._HELP("nonexistent_object")
        assert "Error" in result

    def test_export_no_history(self, magic, console):
        """Test %export with no command history."""
        console.command_history = Mock()
        console.command_history._cmd_history = []
        result = magic._EXPORT()
        assert "No commands to export" in result

    def test_export_with_filepath(self, magic, console):
        """Test %export with filepath argument."""
        console.command_history = Mock()
        console.command_history._cmd_history = ["x = 1", "y = 2"]
        console.export_as_script = Mock(return_value=True)

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            filepath = f.name

        try:
            result = magic._EXPORT(filepath)
            assert "exported successfully" in result
            console.export_as_script.assert_called_once_with(filepath=filepath)
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_cancelled(self, magic, console):
        """Test %export when user cancels dialog."""
        console.command_history = Mock()
        console.command_history._cmd_history = ["x = 1"]
        console.export_as_script = Mock(return_value=False)

        result = magic._EXPORT()
        assert "cancelled" in result

    def test_export_failed_with_filepath(self, magic, console):
        """Test %export failure with provided filepath."""
        console.command_history = Mock()
        console.command_history._cmd_history = ["x = 1"]
        console.export_as_script = Mock(return_value=False)

        result = magic._EXPORT("/some/path/file.py")
        assert "Export failed" in result
