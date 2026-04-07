"""Test autocomplete functionality."""

from unittest.mock import Mock

import pytest
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QPlainTextEdit

from qonsole.autocomplete import COMPLETE_MODE, AutoComplete


class TestAutoComplete:
    """Test autocomplete logic."""

    @pytest.fixture
    def console(self, qtbot):
        """Create a mock console."""

        class MockConsole(QObject):
            def __init__(self):
                super().__init__()
                self.edit = QPlainTextEdit()
                self.interpreter = Mock()
                self.interpreter.get_completions = Mock(return_value=[])
                self._buffer = ""

            def input_buffer(self):
                return self.edit.toPlainText()

            def clear_input_buffer(self):
                pass

        console = MockConsole()
        qtbot.add_widget(console.edit)
        return console

    @pytest.fixture
    def autocomplete(self, console):
        """Create an AutoComplete instance."""
        return AutoComplete(console)

    def test_initialization(self, autocomplete, console):
        """Test autocomplete initializes properly."""
        assert autocomplete.completer is not None
        assert autocomplete.mode in [COMPLETE_MODE.DROPDOWN, COMPLETE_MODE.INLINE]

    def test_get_word_partial(self, autocomplete):
        """Test extracting partial word."""
        buffer = "from math import sq"
        word = autocomplete._get_word_being_completed(buffer)
        assert word == "sq"

    def test_get_word_after_space(self, autocomplete):
        """Test word extraction after space returns empty."""
        buffer = "from math import "
        word = autocomplete._get_word_being_completed(buffer)
        assert word == ""

    def test_get_word_after_dot(self, autocomplete):
        """Test word extraction after dot."""
        buffer = "os.path."
        word = autocomplete._get_word_being_completed(buffer)
        assert word == ""

    def test_completing_property(self, autocomplete):
        """Test the completing property."""
        # Initially popup is not visible
        result = autocomplete.completing()
        assert isinstance(result, bool)

    def test_completion_mode_inline(self, autocomplete):
        """Test inline completion mode."""
        autocomplete.mode = COMPLETE_MODE.INLINE
        assert autocomplete.mode == COMPLETE_MODE.INLINE

    def test_completion_mode_dropdown(self, autocomplete):
        """Test dropdown completion mode."""
        autocomplete.mode = COMPLETE_MODE.DROPDOWN
        assert autocomplete.mode == COMPLETE_MODE.DROPDOWN
