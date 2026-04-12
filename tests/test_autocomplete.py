"""Test autocomplete functionality."""

from unittest.mock import Mock, patch

import pytest
from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtGui import QKeyEvent, QTextCursor
from qtpy.QtWidgets import QPlainTextEdit

from qonsole.autocomplete import AutoComplete


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
                self._prompt_pos = 0

            def input_buffer(self):
                return self.edit.toPlainText()

            def clear_input_buffer(self):
                self.edit.clear()

            def insert_input_text(self, text):
                self.edit.insertPlainText(text)

            def _textCursor(self):
                return self.edit.textCursor()

            def get_completions(self, buffer):
                # Return some sample completions
                return ["sqrt", "square", "sum", "str"]

        console = MockConsole()
        qtbot.add_widget(console.edit)
        return console

    @pytest.fixture
    def autocomplete(self, console):
        """Create an AutoComplete instance."""
        return AutoComplete(console)

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

    def test_get_word_empty_buffer(self, autocomplete):
        """Test word extraction from empty buffer."""
        word = autocomplete._get_word_being_completed("")
        assert word == ""

    def test_get_word_with_dot_prefix(self, autocomplete):
        """Test word extraction with dot prefix."""
        buffer = "os.path.join"
        word = autocomplete._get_word_being_completed(buffer)
        assert word == "join"

    def test_get_word_with_space_prefix(self, autocomplete):
        """Test word extraction with space prefix."""
        buffer = "from os import path"
        word = autocomplete._get_word_being_completed(buffer)
        assert word == "path"

    def test_get_word_no_separator(self, autocomplete):
        """Test word extraction with no separator."""
        buffer = "hello"
        word = autocomplete._get_word_being_completed(buffer)
        assert word == "hello"

    def test_hide_completion_suggestions_no_completer(self, autocomplete):
        """Test hiding suggestions when no completer exists."""
        result = autocomplete.hide_completion_suggestions()
        assert result is False
        assert autocomplete._completing_active is False

    def test_hide_completion_suggestions_with_popup(self, autocomplete, qtbot):
        """Test hiding suggestions when popup is active."""
        # Setup autocomplete with a popup
        autocomplete.init_completion_list(["test", "testing"])
        autocomplete._completing_active = True

        # Simulate popup being visible
        if autocomplete.completer and autocomplete.completer.popup():
            autocomplete.completer.popup().show()
            qtbot.wait(10)

            autocomplete.hide_completion_suggestions()
            assert autocomplete._completing_active is False

    def test_trigger_complete(self, autocomplete, console):
        """Test triggering completion."""
        console.edit.setPlainText("sq")
        autocomplete.trigger_complete()

        # Should have created a completer
        assert autocomplete.completer is not None

    def test_show_completion_suggestions(self, autocomplete, console, qtbot):
        """Test showing completion suggestions."""
        console.edit.setPlainText("s")
        autocomplete.show_completion_suggestions("s")

        # Check that completer was created
        assert autocomplete.completer is not None
        assert autocomplete._completing_active is True

    def test_show_completion_suggestions_no_matches(self, autocomplete):
        """Test showing suggestions when no completions available."""
        with patch.object(autocomplete.parent(), "get_completions", return_value=[]):
            autocomplete.show_completion_suggestions("xyz")
            # Should not activate completion
            assert autocomplete._completing_active is False

    def test_init_completion_list(self, autocomplete, console):
        """Test initializing completion list."""
        words = ["sqrt", "square", "sum"]
        console.edit.setPlainText("sq")

        autocomplete.init_completion_list(words)

        assert autocomplete.completer is not None
        assert autocomplete.completer.widget() == console.edit

    def test_init_completion_list_with_prefix(self, autocomplete, console):
        """Test init with partial word as prefix."""
        console.edit.setPlainText("import sq")
        words = ["sqrt", "square", "sum"]

        autocomplete.init_completion_list(words)

        # Prefix should be set to "sq"
        assert autocomplete.completer.completionPrefix() == "sq"

    def test_handle_tab_key_with_selection(self, autocomplete, console, qtbot):
        """Test Tab key when text is selected."""
        console.edit.setPlainText("selected")
        cursor = console.edit.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        console.edit.setTextCursor(cursor)

        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.handle_tab_key(event)

        # Should not handle when selection exists
        assert result is False

    def test_handle_tab_key_trigger(self, autocomplete, console):
        """Test Tab key triggering completion."""
        console.edit.setPlainText("sq")

        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.handle_tab_key(event)

        assert result is True
        # Should have created completer
        assert autocomplete.completer is not None

    def test_handle_complete_key_no_completion(self, autocomplete):
        """Test Enter/Return when not completing."""
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.handle_complete_key(event)

        assert result is False

    def test_handle_complete_key_while_completing(self, autocomplete, console, qtbot):
        """Test Enter/Return while completing."""
        # Setup active completion
        console.edit.setPlainText("sq")
        autocomplete.show_completion_suggestions("sq")

        if autocomplete.completing():
            event = QKeyEvent(
                QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
            )
            result = autocomplete.handle_complete_key(event)

            assert result is True

    def test_insert_completion(self, autocomplete, console):
        """Test inserting a completion."""
        console.edit.setPlainText("sq")

        # Move cursor to end
        cursor = console.edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        console.edit.setTextCursor(cursor)

        autocomplete.insert_completion("sqrt")

        # Should replace "sq" with "sqrt"
        text = console.edit.toPlainText()
        assert "sqrt" in text
        assert text.endswith("sqrt")

    def test_insert_completion_no_partial(self, autocomplete, console):
        """Test inserting completion with no partial word."""
        console.edit.setPlainText("import ")

        autocomplete.insert_completion("math")

        text = console.edit.toPlainText()
        assert "math" in text

    def test_complete_method(self, autocomplete, console, qtbot):
        """Test the complete() method."""
        console.edit.setPlainText("sq")
        autocomplete.show_completion_suggestions("sq")

        if autocomplete.completing():
            # Simulate selecting an item
            autocomplete.complete()

            # Text should be updated
            assert autocomplete._completing_active is False

    def test_key_pressed_handler_tab(self, autocomplete):
        """Test key handler for Tab key."""
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.key_pressed_handler(event)

        assert result is True

    def test_key_pressed_handler_return(self, autocomplete):
        """Test key handler for Return key."""
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.key_pressed_handler(event)

        # Should return False when not completing
        assert result is False

    def test_key_pressed_handler_escape(self, autocomplete):
        """Test key handler for Escape key."""
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.key_pressed_handler(event)

        # Should return False when no popup
        assert result is False

    def test_key_pressed_handler_escape_with_popup(self, autocomplete, console):
        """Test Escape key hiding popup."""
        console.edit.setPlainText("sq")
        autocomplete.show_completion_suggestions("sq")

        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        )
        autocomplete.key_pressed_handler(event)

        # Should hide completion
        assert autocomplete._completing_active is False

    def test_key_pressed_handler_space(self, autocomplete):
        """Test key handler for Space key."""
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.key_pressed_handler(event)

        # Should return False when not completing
        assert result is False

    def test_key_pressed_handler_other_key(self, autocomplete):
        """Test key handler for other keys."""
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.key_pressed_handler(event)

        # Should return False for regular keys
        assert result is False

    def test_event_filter_non_keypress(self, autocomplete, console):
        """Test event filter with non-keypress events."""
        event = QEvent(QEvent.Type.MouseButtonPress)
        result = autocomplete.eventFilter(console.edit, event)

        assert result is False

    def test_event_filter_from_edit_widget(self, autocomplete, console):
        """Test event filter from edit widget."""
        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier
        )
        result = autocomplete.eventFilter(console.edit, event)

        # Tab key should be handled
        assert result is True

    def test_on_text_changed_not_completing(self, autocomplete):
        """Test text changed when not completing."""
        autocomplete._completing_active = False
        autocomplete._on_text_changed()

        # Should do nothing
        assert autocomplete.completer is None

    def test_on_text_changed_while_completing(self, autocomplete, console, qtbot):
        """Test text changed while completing updates prefix."""
        console.edit.setPlainText("sq")
        autocomplete.show_completion_suggestions("sq")

        if autocomplete._completing_active and autocomplete.completer:
            # Change text
            console.edit.setPlainText("squ")
            autocomplete._on_text_changed()

            # Prefix should be updated
            assert autocomplete.completer.completionPrefix() == "squ"

    def test_on_text_changed_no_matches(self, autocomplete, console, qtbot):
        """Test text changed with no matches hides popup."""
        console.edit.setPlainText("sq")
        autocomplete.show_completion_suggestions("sq")

        if autocomplete._completing_active:
            # Change to something with no completions
            console.edit.setPlainText("xyzabc")

            with patch.object(
                autocomplete.completer, "completionCount", return_value=0
            ):
                autocomplete._on_text_changed()

                # Should hide completion
                assert autocomplete._completing_active is False

    def test_completing_no_completer(self, autocomplete):
        """Test completing() when completer is None."""
        autocomplete.completer = None
        assert autocomplete.completing() is False

    def test_completing_no_popup(self, autocomplete):
        """Test completing() when popup is None."""
        autocomplete.completer = Mock()
        autocomplete.completer.popup = Mock(return_value=None)
        assert autocomplete.completing() is False

    def test_event_filter_popup_navigation_keys(self, autocomplete, console, qtbot):
        """Test that navigation keys in popup are not filtered."""
        # Setup completion with popup
        console.edit.setPlainText("sq")
        autocomplete.show_completion_suggestions("sq")

        if autocomplete.completer and autocomplete.completer.popup():
            popup = autocomplete.completer.popup()

            # Test navigation keys should not be filtered
            for key in [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Return]:
                event = QKeyEvent(
                    QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier
                )
                result = autocomplete.eventFilter(popup, event)
                assert result is False

    def test_event_filter_popup_escape(self, autocomplete, console, qtbot):
        """Test Escape key in popup closes it."""
        console.edit.setPlainText("sq")
        autocomplete.show_completion_suggestions("sq")

        if autocomplete.completer and autocomplete.completer.popup():
            popup = autocomplete.completer.popup()

            event = QKeyEvent(
                QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
            )
            result = autocomplete.eventFilter(popup, event)

            assert result is True
            assert autocomplete._completing_active is False

    def test_show_completion_closes_existing_popup(self, autocomplete, console, qtbot):
        """Test that showing completion closes any existing popup."""
        # Show first completion
        console.edit.setPlainText("sq")
        autocomplete.show_completion_suggestions("sq")

        # Show again (should close first)
        autocomplete.show_completion_suggestions("st")

        assert autocomplete.completer is not None
