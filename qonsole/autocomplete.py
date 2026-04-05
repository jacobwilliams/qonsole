"""Auto-completion functionality for the console.

Provides auto-completion support with dropdown and inline modes,
using Jedi for intelligent Python code completion.
"""

from typing import TYPE_CHECKING, Optional

from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtWidgets import QCompleter

from .text import columnize, long_substr

if TYPE_CHECKING:
    from .console import BaseConsole


class COMPLETE_MODE:
    """Constants for auto-completion display modes.

    Attributes:
        DROPDOWN: Show completions in a dropdown popup menu.
        INLINE: Show completions inline below the current line.
    """

    DROPDOWN: int = 1
    INLINE: int = 2


class AutoComplete(QObject):
    """Auto-completion handler for the console.

    Manages code completion using Jedi, supporting both dropdown and inline
    completion modes. Handles Tab key for triggering completions and displays
    completion suggestions.
    """

    def __init__(self, parent: "BaseConsole") -> None:
        """Initialize the auto-complete handler.

        Args:
            parent: Parent console widget.
        """
        super().__init__(parent)
        self.mode: int = COMPLETE_MODE.INLINE
        self.completer: Optional[QCompleter] = None
        self._last_key: Optional[int] = None

        parent.edit.installEventFilter(self)
        self.init_completion_list([])

    def eventFilter(self, widget: QObject, event: QEvent) -> bool:
        """Filter events to intercept key presses for completion.

        Args:
            widget: Widget that generated the event.
            event: QEvent to filter.

        Returns:
            True if the event was handled and should be filtered, False otherwise.
        """
        if event.type() == QEvent.KeyPress:
            return bool(self.key_pressed_handler(event))
        return False

    def key_pressed_handler(self, event: QEvent) -> bool:
        """Handle key press events for completion.

        Intercepts Tab, Enter, Return, Space, and Escape keys to manage
        completion behavior.

        Args:
            event: QKeyEvent to handle.

        Returns:
            True if the event was handled, False otherwise.
        """
        intercepted = False
        key = event.key()

        if key == Qt.Key_Tab:
            intercepted = self.handle_tab_key(event)
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            intercepted = self.handle_complete_key(event)
        elif key == Qt.Key_Escape:
            intercepted = self.hide_completion_suggestions()

        self._last_key = key
        return intercepted

    def handle_tab_key(self, event: QEvent) -> bool:
        """Handle Tab key press for triggering or accepting completions.

        Args:
            event: QKeyEvent for the Tab press.

        Returns:
            True if the event was handled, False otherwise.
        """
        if self.parent()._textCursor().hasSelection():
            return False

        if self.mode == COMPLETE_MODE.DROPDOWN:
            if self.parent().input_buffer().split("\n")[-1].strip():
                if self.completing():
                    self.complete()
                else:
                    self.trigger_complete()

                event.accept()
                return True

        elif self.mode == COMPLETE_MODE.INLINE:
            if self._last_key == Qt.Key_Tab:
                self.trigger_complete()

            event.accept()
            return True

        return False

    def handle_complete_key(self, event: QEvent) -> bool:
        """Handle Enter/Return/Space keys to accept a completion.

        Args:
            event: QKeyEvent for the key press.

        Returns:
            True if the event was handled, False otherwise.
        """
        if self.completing():
            self.complete()
            event.accept()
            return True
        return False

    def _get_word_being_completed(self, _buffer: str) -> str:
        """Extract the word currently being completed from the buffer.

        Returns the partial word after the last separator (space or dot).
        Returns empty string if buffer ends with a separator.

        Args:
            _buffer: Current input buffer string.

        Returns:
            The partial word being completed, or empty string.
        """
        # Check if buffer ends with a separator - if so, we're starting fresh
        if not _buffer or _buffer[-1] in (" ", "."):
            return ""

        # Find the last separator (space or dot)
        dot_idx = _buffer.rfind(".")
        space_idx = _buffer.rfind(" ")
        sep_idx = max(dot_idx, space_idx)

        # Return word after the last separator
        return _buffer[sep_idx + 1 :].strip() if sep_idx >= 0 else _buffer.strip()

    def init_completion_list(self, words: list[str]) -> None:
        """Initialize the QCompleter with a list of completion words.

        Creates a new completer configured for the current completion mode
        and sets up the appropriate completion prefix.

        Args:
            words: List of completion word strings.
        """
        # Create a new completer (old one will be garbage collected)
        self.completer = QCompleter(words, self)

        # Extract just the word being completed to use as prefix
        _buffer = self.parent().input_buffer()
        word_being_completed = self._get_word_being_completed(_buffer)

        self.completer.setCompletionPrefix(word_being_completed)
        self.completer.setWidget(self.parent().edit)
        self.completer.setCaseSensitivity(Qt.CaseSensitive)
        self.completer.setModelSorting(QCompleter.CaseSensitivelySortedModel)

        if self.mode == COMPLETE_MODE.DROPDOWN:
            self.completer.setCompletionMode(QCompleter.PopupCompletion)
            self.completer.activated[str].connect(self.insert_completion)
        else:
            self.completer.setCompletionMode(QCompleter.InlineCompletion)

    def trigger_complete(self) -> None:
        """Trigger the auto-completion process.

        Fetches completion suggestions for the current input buffer
        and displays them.
        """
        _buffer = self.parent().input_buffer()
        self.show_completion_suggestions(_buffer)

    def show_completion_suggestions(self, _buffer: str) -> None:
        """Show completion suggestions for the given buffer.

        Fetches completions from the parent console, finds the common prefix,
        and displays suggestions in either dropdown or inline mode.

        Args:
            _buffer: Current input buffer to get completions for.
        """
        words = self.parent().get_completions(_buffer)

        # No words to show, just return
        if len(words) == 0:
            return

        # Close any popups before creating a new one
        if self.completer.popup():
            self.completer.popup().close()

        self.init_completion_list(words)

        leastcmn = long_substr(words)
        # Only insert the common substring if it's not empty
        # This handles "from os import " where there's no partial word yet
        if leastcmn:
            self.insert_completion(leastcmn)

        # If only one word to complete, just return and don't display options
        if len(words) == 1:
            return

        if self.mode == COMPLETE_MODE.DROPDOWN:
            cr = self.parent().edit.cursorRect()
            sbar_w = self.completer.popup().verticalScrollBar()
            popup_width = self.completer.popup().sizeHintForColumn(0)
            popup_width += sbar_w.sizeHint().width()
            cr.setWidth(popup_width)
            self.completer.complete(cr)
        elif self.mode == COMPLETE_MODE.INLINE:
            cl = columnize(words, colsep="  |  ")
            self.parent()._insert_output_text(
                "\n\n" + cl + "\n", lf=True, keep_buffer=True
            )

    def hide_completion_suggestions(self) -> bool:
        """Hide the completion suggestions popup.

        Returns:
            True if a popup was hidden, False otherwise.
        """
        if self.completing():
            self.completer.popup().close()
            return True
        return False

    def completing(self) -> bool:
        """Check if completion popup is currently visible.

        Returns:
            True if in dropdown mode and popup is visible, False otherwise.
        """
        if self.mode == COMPLETE_MODE.DROPDOWN:
            return self.completer.popup() and self.completer.popup().isVisible()
        else:
            return False

    def insert_completion(self, completion: str) -> None:
        """Insert a completion string into the editor.

        Replaces the partial word with the full completion and positions
        the cursor appropriately.

        Args:
            completion: The completion string to insert.
        """
        # Close the popup first if it's visible
        if self.completing():
            self.completer.popup().hide()

        _buffer = self.parent().input_buffer()
        word_being_completed = self._get_word_being_completed(_buffer)

        if self.mode == COMPLETE_MODE.DROPDOWN:
            # If we have a partial word, remove it first before inserting
            if len(word_being_completed) > 0:
                # Remove the partial word by moving cursor back and deleting
                cursor = self.parent()._textCursor()
                for _ in range(len(word_being_completed)):
                    cursor.deletePreviousChar()

            # Insert the full completion word
            self.parent().insert_input_text(completion)
        elif self.mode == COMPLETE_MODE.INLINE:
            # Preserve the prefix before the word being completed
            _buffer_stripped = _buffer.strip()
            prefix_len = len(_buffer_stripped) - len(word_being_completed)
            prefix = _buffer_stripped[:prefix_len]

            # If original buffer ends with space and we have no partial word,
            # the prefix should include that space for proper reconstruction
            if len(word_being_completed) == 0 and _buffer.endswith(" "):
                prefix += " "

            self.parent().clear_input_buffer()
            self.parent().insert_input_text(prefix + completion)

            # Get completions for the full completed line
            words = self.parent().get_completions(prefix + completion)

            if len(words) == 1:
                self.parent().insert_input_text(" ")

    def complete(self) -> None:
        """Complete with the currently selected item in the popup.

        Only applicable in dropdown mode. Inserts the selected completion
        from the popup menu.
        """
        if self.completing() and self.mode == COMPLETE_MODE.DROPDOWN:
            index = self.completer.popup().currentIndex()
            model = self.completer.completionModel()
            word = model.itemData(index)[0]
            self.insert_completion(word)
