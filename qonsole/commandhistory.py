"""Command history management for the console.

Provides the CommandHistory class for tracking and navigating through
previously executed commands.
"""

from typing import TYPE_CHECKING

from qtpy.QtCore import QObject

if TYPE_CHECKING:
    from .console import BaseConsole


class CommandHistory(QObject):
    """Manages command history navigation for the console.

    Tracks previously executed commands and allows navigation through
    the history using up/down arrow keys.
    """

    def __init__(self, parent: "BaseConsole") -> None:
        """Initialize the command history.

        Args:
            parent: Parent console widget.
        """
        super().__init__(parent)
        self._cmd_history: list[str] = []
        self._idx: int = 0
        self._pending_input: str = ""

    def add(self, str_: str) -> None:
        """Add a command to the history.

        Args:
            str_: Command string to add to history.
        """
        if str_:
            self._cmd_history.append(str_)

        self._pending_input = ""
        self._idx = len(self._cmd_history)

    def inc(self) -> None:
        """Move forward in history (towards more recent commands).

        Updates the editor with the command at the new position.
        """
        # index starts at 0 so + 1 to make sure that we are within the
        # limits of the list
        if self._cmd_history:
            self._idx = min(self._idx + 1, len(self._cmd_history))
            self._insert_in_editor(self.current())

    def dec(self, _input: str) -> None:
        """Move backward in history (towards older commands).

        Saves the current input before navigating and updates the editor
        with the command at the new position.

        Args:
            _input: Current input text to save if at the end of history.
        """
        if self._idx == len(self._cmd_history):
            self._pending_input = _input
        if len(self._cmd_history) and self._idx > 0:
            self._idx -= 1
            self._insert_in_editor(self.current())

    def current(self) -> str:
        """Get the command at the current history position.

        Returns:
            The command string at the current index, or the pending input
            if at the end of history.
        """
        if self._idx == len(self._cmd_history):
            return self._pending_input
        else:
            return self._cmd_history[self._idx]

    def _insert_in_editor(self, str_: str) -> None:
        """Replace editor content with the given string.

        Args:
            str_: String to insert into the editor.
        """
        self.parent().clear_input_buffer()
        self.parent().insert_input_text(str_)
