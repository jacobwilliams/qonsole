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
        console.interpreter = Mock()
        console.interpreter.locals = {}
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
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = magic._CD(tmpdir)
                # Normalize paths (macOS has /private/var and /var symlinks)
                assert os.path.realpath(tmpdir) == os.path.realpath(os.getcwd())
        finally:
            os.chdir(original)  # Restore

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
