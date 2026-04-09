"""Auto-completion functionality for the console.

Provides auto-completion dropdown support,
using Jedi for intelligent Python code completion.
"""

from typing import TYPE_CHECKING, Optional

from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QCompleter

if TYPE_CHECKING:
    from .console import BaseConsole


class AutoComplete(QObject):
    """Auto-completion handler for the console.

    Manages code completion using Jedi, supporting a dropdown
    completion mode. Handles Tab key for triggering completions and displays
    completion suggestions.
    """

    def __init__(self, parent: "BaseConsole") -> None:
        """Initialize the auto-complete handler.

        Args:
            parent: Parent console widget.
        """
        super().__init__(parent)
        self.completer: Optional[QCompleter] = None
        self._last_key: Optional[int] = None
        self._completing_active: bool = False

        parent.edit.installEventFilter(self)
        parent.edit.textChanged.connect(self._on_text_changed)
        self.init_completion_list([])

    def eventFilter(self, widget: QObject, event: QEvent) -> bool:
        """Filter events to intercept key presses for completion.

        Handles events from both the edit widget and the completion popup.
        For the popup, forwards typing events back to the edit widget while
        preserving navigation keys.

        Args:
            widget: Widget that generated the event.
            event: QEvent to filter.

        Returns:
            True if the event was handled and should be filtered, False otherwise.
        """
        if event.type() != QEvent.KeyPress:
            return False

        # Check if this event is from the popup
        if self.completer and widget == self.completer.popup():
            key = event.key()
            # Navigation keys and selection keys stay with the popup
            if key in (
                Qt.Key_Up,
                Qt.Key_Down,
                Qt.Key_PageUp,
                Qt.Key_PageDown,
                Qt.Key_Return,
                Qt.Key_Enter,
            ):
                return False
            # Escape to close
            if key == Qt.Key_Escape:
                self.hide_completion_suggestions()
                return True
            # For everything else (typing, backspace, Tab, etc.),
            # forward to edit widget
            from qtpy.QtCore import QCoreApplication

            QCoreApplication.sendEvent(self.parent().edit, event)
            return True

        # Event from edit widget
        return bool(self.key_pressed_handler(event))

    def key_pressed_handler(self, event: QEvent) -> bool:
        """Handle key press events for completion.

        Intercepts Tab, Enter, Return, Space, and Escape keys to manage
        completion behavior. Regular typing is allowed to pass through
        and the completion list updates automatically via textChanged signal.

        Args:
            event: QKeyEvent to handle.

        Returns:
            True if the event was handled, False otherwise.
        """
        key = event.key()
        self._last_key = key

        if key == Qt.Key_Tab:
            return self.handle_tab_key(event)
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            return self.handle_complete_key(event)
        if key == Qt.Key_Escape:
            return self.hide_completion_suggestions()

        return False

    def handle_tab_key(self, event: QEvent) -> bool:
        """Handle Tab key press for triggering or accepting completions.

        Args:
            event: QKeyEvent for the Tab press.

        Returns:
            True if the event was handled, False otherwise.
        """
        if self.parent()._textCursor().hasSelection():
            return False

        event.accept()

        self.complete() if self.completing() else self.trigger_complete()

        return True

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
        if not _buffer or _buffer[-1] in " .":
            return ""

        sep_idx = max(_buffer.rfind("."), _buffer.rfind(" "))
        return _buffer[sep_idx + 1 :].strip() if sep_idx >= 0 else _buffer.strip()

    def _on_text_changed(self) -> None:
        """Handle text changes in the edit widget.

        When the completion popup is visible and text changes, update the
        completion prefix to filter the list based on what's been typed,
        and automatically select the first matching item.
        """
        if not self._completing_active:
            return

        word_being_completed = self._get_word_being_completed(
            self.parent().input_buffer()
        )
        self.completer.setCompletionPrefix(word_being_completed)

        if self.completer.completionCount() == 0:
            self.hide_completion_suggestions()
            return

        popup = self.completer.popup()
        if popup:
            # Ensure popup is visible at current cursor position
            if not popup.isVisible():
                self.completer.complete(self.parent().edit.cursorRect())
            # Select the first matching item
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))

    def init_completion_list(self, words: list[str]) -> None:
        """Initialize the QCompleter with a list of completion words.

        Creates a new completer configured for the current completion mode
        and sets up the appropriate completion prefix.

        Args:
            words: List of completion word strings.
        """
        self.completer = QCompleter(words, self)
        self.completer.setCompletionPrefix(
            self._get_word_being_completed(self.parent().input_buffer())
        )
        self.completer.setWidget(self.parent().edit)
        self.completer.setCaseSensitivity(Qt.CaseSensitive)
        self.completer.setModelSorting(QCompleter.CaseSensitivelySortedModel)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.activated[str].connect(self.insert_completion)
        popup = self.completer.popup()
        if popup:
            popup.installEventFilter(self)
            popup.setFocusPolicy(Qt.NoFocus)
            popup.setFocusProxy(self.parent().edit)

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
        if not words:
            return

        if self.completer.popup():
            self.completer.popup().close()

        self.init_completion_list(words)

        if self.completer.completionCount() == 0:
            return

        popup = self.completer.popup()
        cr = self.parent().edit.cursorRect()
        cr.setWidth(
            popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width()
        )
        self.completer.complete(cr)
        self._completing_active = True
        if popup:
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))

    def hide_completion_suggestions(self) -> bool:
        """Hide the completion suggestions popup.

        Returns:
            True if a popup was hidden, False otherwise.
        """
        self._completing_active = False
        if self.completing():
            self.completer.popup().close()
            return True
        return False

    def completing(self) -> bool:
        """Check if completion popup is currently visible.

        Returns:
            True if in dropdown mode and popup is visible, False otherwise.
        """
        return self.completer.popup() and self.completer.popup().isVisible()

    def insert_completion(self, completion: str) -> None:
        """Insert a completion string into the editor.

        Replaces the partial word with the full completion and positions
        the cursor appropriately.

        Args:
            completion: The completion string to insert.
        """
        if self.completing():
            self.completer.popup().hide()

        self._completing_active = False

        _buffer = self.parent().input_buffer()
        word_being_completed = self._get_word_being_completed(_buffer)

        if word_being_completed:
            cursor = self.parent()._textCursor()
            cursor.movePosition(
                QTextCursor.Left, QTextCursor.KeepAnchor, len(word_being_completed)
            )
            cursor.removeSelectedText()
        self.parent().insert_input_text(completion)

    def complete(self) -> None:
        """Complete with the currently selected item in the popup.

        Only applicable in dropdown mode. Inserts the selected completion
        from the popup menu.
        """
        if self.completing():
            index = self.completer.popup().currentIndex()
            model = self.completer.completionModel()
            word = model.itemData(index)[0]
            self.insert_completion(word)
