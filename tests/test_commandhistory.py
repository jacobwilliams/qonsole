"""Test command history functionality."""

from unittest.mock import Mock

import pytest
from qtpy.QtCore import QObject

from qonsole.commandhistory import CommandHistory


class TestCommandHistory:
    """Test command history."""

    @pytest.fixture
    def console(self):
        """Create a mock console."""

        class MockConsole(QObject):
            def __init__(self):
                super().__init__()
                self.edit = Mock()
                self.edit.toPlainText = Mock(return_value="")
                self.edit.setPlainText = Mock()

            def clear_input_buffer(self):
                pass

            def insert_input_text(self, text):
                pass

        return MockConsole()

    @pytest.fixture
    def history(self, console):
        """Create a CommandHistory instance."""
        return CommandHistory(console)

    def test_add_command(self, history):
        """Test adding commands."""
        history.add("print('hello')")
        history.add("x = 42")
        assert len(history._cmd_history) == 2

    def test_add_empty_not_stored(self, history):
        """Test that empty commands are not stored."""
        history.add("")
        assert len(history._cmd_history) == 0

    def test_navigation(self, history, console):
        """Test navigation through history."""
        history.add("cmd1")
        history.add("cmd2")
        history.add("cmd3")

        # dec() moves backward and requires current input
        history.dec("")
        assert history._idx == 2  # Should be at cmd3

        history.dec("")
        assert history._idx == 1  # Should be at cmd2
