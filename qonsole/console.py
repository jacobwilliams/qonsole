"""Interactive console widget for Qt applications.

Provides BaseConsole and PythonConsole classes for embedding an interactive
Python console with syntax highlighting, command history, auto-completion,
and magic commands.
"""

import ctypes
import subprocess
import threading
from abc import abstractmethod
from typing import Any, Callable, Optional, Union

from jedi import Interpreter, settings
from pygments.styles import get_style_by_name
from qtpy.QtCore import QEvent, Qt, QThread, Slot
from qtpy.QtGui import QClipboard, QColor, QFont, QFontMetrics, QTextCursor
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
)

from .autocomplete import AutoComplete
from .commandhistory import CommandHistory
from .export import export_session
from .highlighter import (
    ErrorHighlightData,
    NoHighlightData,
    PromptHighlighter,
    PythonHighlighter,
)
from .interpreter import PythonInterpreter
from .magic import MagicCmds
from .prompt import PromptArea
from .stream import Stream

settings.case_insensitive_completion = False

try:  # PyQt >= 5.11
    QueuedConnection = Qt.ConnectionType.QueuedConnection
except AttributeError:  # PyQt < 5.11
    QueuedConnection = Qt.QueuedConnection


class BaseConsole(QFrame):
    """Base class for implementing a GUI console.

    Provides the core functionality for a console widget including input/output
    handling, command history, auto-completion, and magic commands. Subclasses
    must implement abstract methods for execution and completion.
    """

    def __init__(
        self,
        parent: Optional[QFrame] = None,
        inprompt: Optional[str] = None,
        outprompt: Optional[str] = None,
        welcome_message: Optional[str] = None,
        pygments_style: Optional[str] = None,
        preamble: Optional[list[str]] = None,
    ) -> None:
        """Initialize the base console.

        Args:
            parent: Parent widget. Defaults to None.
            inprompt: Input prompt template. If None, uses 'IN [%d]: ' where %d
                is the current line number. Defaults to None.
            outprompt: Output prompt template. If None, uses 'OUT[%d]: ' where %d
                is the current line number. Defaults to None.
            welcome_message: Welcome message to display at startup. Not syntax
                highlighted. Defaults to None.
            pygments_style: Name of Pygments style (e.g., 'monokai', 'vim').
                If None, uses 'default' style. Defaults to None.
            preamble: Optional list of lines to add at the top of exported
                scripts/notebooks (e.g., imports). Defaults to None.
        """
        super().__init__(parent)

        # Use default Pygments style if none specified
        if pygments_style is None:
            pygments_style = "default"

        self.edit = edit = InputArea()
        self.pbar = pbar = PromptArea(
            edit,
            self._get_prompt_text,
            PromptHighlighter(pygments_style=pygments_style),
        )

        layout = QHBoxLayout()
        layout.addWidget(pbar)
        layout.addWidget(edit)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # a list of tuples that tracks the prompt text for each line.
        # Each tuple is: (prompt_text, is_output), where:
        #  * `prompt_text` is the text of the prompt
        #  * `is_output` is a boolean
        #    indicating whether the line is an output
        #    line (True) or an input line (False)
        self._prompt_doc: list[tuple[str, bool]] = [("", False)]
        self._prompt_pos: int = 0
        self._output_inserted: bool = False
        self._tab_chars = 4 * " "
        self._ctrl_d_exits = False
        self._copy_buffer = ""

        self._last_input = ""
        self._more = False
        self._current_line = 0

        self._ps1 = inprompt or "IN [%d]:"
        self._ps1 = self._ps1.strip() + " "
        self._ps2 = "...: "
        self._ps_out = outprompt or "OUT[%d]:"
        self._ps_out = self._ps_out.strip() + " "
        self._ps = self.in_prompt()

        self.magic = MagicCmds(self)
        self.add_magic_command = self.magic.add_magic_command

        self.stdin = Stream()
        self.stdout = Stream()
        self.stdout.write_event.connect(self._stdout_data_handler)
        self._current_output_is_error = False  # Track if current output is error

        # Track outputs for each command (for notebook export)
        # List of (command, output, is_error) tuples
        self._command_outputs: list[tuple[str, str, bool]] = []
        # Buffer for current command's output
        self._current_command_output: list[str] = []

        # show frame around both child widgets:
        self.setFrameStyle(edit.frameStyle())
        edit.setFrameStyle(QFrame.NoFrame)

        font = edit.document().defaultFont()
        font.setFamily("Courier New")
        font_width = QFontMetrics(font).width("M")
        self.setFont(font)

        geometry = edit.geometry()
        geometry.setWidth(font_width * 80 + 20)
        geometry.setHeight(font_width * 40)
        edit.setGeometry(geometry)
        edit.resize(font_width * 80 + 20, font_width * 40)

        edit.setReadOnly(True)
        edit.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.setFocusPolicy(Qt.NoFocus)
        pbar.setFocusPolicy(Qt.NoFocus)
        edit.setFocusPolicy(Qt.StrongFocus)
        edit.setFocus()

        edit.installEventFilter(self)
        self._key_event_handlers = self._get_key_event_handlers()

        self.command_history = CommandHistory(self)
        self.auto_complete = AutoComplete(self)

        # Store welcome message to be displayed by subclass if needed
        self._welcome_message = welcome_message

        # Store preamble lines for export
        self._preamble = preamble if preamble is not None else []

        self._show_ps()

    def out_prompt(self) -> str:
        """Get the formatted output prompt.

        Returns:
            Formatted output prompt string with current line number.
        """
        try:
            # may depend on current line:
            return self._ps_out % self._current_line
        except TypeError:
            return self._ps_out
            # In case the provided format does not include a placeholder, just
            # take the template string

    def in_prompt(self) -> str:
        """Get the formatted input prompt.

        Returns:
            Formatted input prompt string with current line number.
        """
        try:
            return self._ps1 % self._current_line
        except TypeError:
            return self._ps1

    def setFont(self, font: QFont) -> None:
        """Set the console font.

        Args:
            font: QFont to use. Should be monospace for best results.
        """
        self.edit.document().setDefaultFont(font)
        self.edit.setFont(font)
        super().setFont(font)

    def eventFilter(self, edit: Any, event: QEvent) -> bool:
        """Filter events from the input control.

        Args:
            edit: Widget that generated the event.
            event: QEvent to filter.

        Returns:
            True if event was handled, False otherwise.
        """
        if event.type() == QEvent.KeyPress:
            return bool(self._filter_keyPressEvent(event))
        elif event.type() == QEvent.MouseButtonPress:
            return bool(self._filter_mousePressEvent(event))
        else:
            return False

    def _textCursor(self) -> QTextCursor:
        """Get the text cursor from the edit widget.

        Returns:
            QTextCursor for the edit area.
        """
        return self.edit.textCursor()

    def _setTextCursor(self, cursor: QTextCursor) -> None:
        """Set the text cursor in the edit widget.

        Args:
            cursor: QTextCursor to set.
        """
        self.edit.setTextCursor(cursor)

    def ensureCursorVisible(self) -> None:
        """Ensure the cursor is visible in the edit widget."""
        self.edit.ensureCursorVisible()

    def _update_ps(self, _more: bool) -> None:
        # We need to show the more prompt of the input was incomplete
        # If the input is complete increase the input number and show
        # the in prompt
        if not _more:
            self._ps = self.in_prompt()
        else:
            # Align continuation prompt with input prompt
            padding = max(0, len(self._ps) - len(self._ps2))
            self._ps = padding * " " + self._ps2

    @Slot(object)
    def _finish_command(self, result: Any) -> None:
        # Check if there was an error before clearing the flag
        had_exception = self._current_output_is_error
        self._current_output_is_error = False

        if result is not None:
            # Add repr to output buffer before inserting to console
            result_str = repr(result)
            self._current_command_output.append(result_str)
            self._insert_output_text(result_str, prompt=self.out_prompt())
            self._insert_output_text("\n")

        # Store the command and its output for export
        if self._last_input:
            output_text = "".join(self._current_command_output)
            self._command_outputs.append((self._last_input, output_text, had_exception))

        # Clear the output buffer for next command
        self._current_command_output = []

        if not had_exception and self._last_input:
            self._current_line += 1
        self._more = False
        self._show_cursor()
        self._update_ps(self._more)
        self._show_ps()

    @Slot()
    def _error_started(self) -> None:
        """Called when the interpreter is about to write error output."""
        self._current_output_is_error = True

    def _show_ps(self) -> None:
        if self._output_inserted and not self._more:
            self._insert_output_text("\n")
        self._insert_prompt_text(self._ps, is_output=False)

    def _get_key_event_handlers(self) -> dict[int, Callable[[Any], Any]]:
        return {
            Qt.Key_Escape: self._handle_escape_key,
            Qt.Key_Return: self._handle_enter_key,
            Qt.Key_Enter: self._handle_enter_key,
            Qt.Key_Backspace: self._handle_backspace_key,
            Qt.Key_Delete: self._handle_delete_key,
            Qt.Key_Home: self._handle_home_key,
            Qt.Key_Tab: self._handle_tab_key,
            Qt.Key_Backtab: self._handle_backtab_key,
            Qt.Key_Up: self._handle_up_key,
            Qt.Key_Down: self._handle_down_key,
            Qt.Key_Left: self._handle_left_key,
            Qt.Key_D: self._handle_d_key,
            Qt.Key_C: self._handle_c_key,
            Qt.Key_V: self._handle_v_key,
            Qt.Key_U: self._handle_u_key,
        }

    def insertFromMimeData(self, mime_data: Any) -> None:
        if mime_data and mime_data.hasText():
            self.insert_input_text(mime_data.text())

    def _filter_mousePressEvent(self, event: QEvent) -> bool:
        if event.button() == Qt.MiddleButton:
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData(QClipboard.Selection)
            self.insertFromMimeData(mime_data)
            return True
        return False

    def _filter_keyPressEvent(self, event: QEvent) -> bool:
        key = event.key()
        event.ignore()

        if self._executing():
            # ignore all key presses while executing, except for Ctrl-C
            if event.modifiers() == Qt.ControlModifier and key == Qt.Key_C:
                self._handle_ctrl_c()
            return True

        handler = self._key_event_handlers.get(key)
        intercepted = handler and handler(event)

        # Assumes that Control+Key is a movement command, i.e. should not be
        # handled as text insertion. However, on win10 AltGr is reported as
        # Alt+Control which is why we handle this case like regular
        # keypresses, see #53:
        if (
            not event.modifiers() & Qt.ControlModifier
            or event.modifiers() & Qt.AltModifier
        ):
            self._keep_cursor_in_buffer()

            if not intercepted and event.text():
                intercepted = True
                self.insert_input_text(event.text())

        return bool(intercepted)

    def _handle_escape_key(self, event: QEvent) -> bool:
        return True

    def _handle_enter_key(self, event: QEvent) -> bool:
        if event.modifiers() & Qt.ShiftModifier:
            self.insert_input_text("\n")
        else:
            cursor = self._textCursor()
            cursor.movePosition(QTextCursor.End)
            self._setTextCursor(cursor)
            buffer = self.input_buffer()
            self._hide_cursor()
            self.insert_input_text("\n", show_ps=False)
            self.process_input(buffer)
        return True

    def _handle_backspace_key(self, event: QEvent) -> bool:
        self._keep_cursor_in_buffer()
        cursor = self._textCursor()
        offset = self.cursor_offset()
        if not cursor.hasSelection() and offset >= 1:
            tab = self._tab_chars
            buf = self._get_line_until_cursor()
            if event.modifiers() == Qt.ControlModifier:
                cursor.movePosition(QTextCursor.PreviousWord, QTextCursor.KeepAnchor, 1)
                self._keep_cursor_in_buffer()
            else:
                # delete spaces to previous tabstop boundary:
                tabstop = len(buf) % len(tab) == 0
                num = len(tab) if tabstop and buf.endswith(tab) else 1
                cursor.movePosition(
                    QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor, num
                )
        self._remove_selected_input(cursor)
        return True

    def _handle_delete_key(self, event: QEvent) -> bool:
        self._keep_cursor_in_buffer()
        cursor = self._textCursor()
        offset = self.cursor_offset()
        if not cursor.hasSelection() and offset < len(self.input_buffer()):
            tab = self._tab_chars
            left = self._get_line_until_cursor()
            right = self._get_line_after_cursor()
            if event.modifiers() == Qt.ControlModifier:
                cursor.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor, 1)
                self._keep_cursor_in_buffer()
            else:
                # delete spaces to next tabstop boundary:
                tabstop = len(left) % len(tab) == 0
                num = len(tab) if tabstop and right.startswith(tab) else 1
                cursor.movePosition(
                    QTextCursor.NextCharacter, QTextCursor.KeepAnchor, num
                )
        self._remove_selected_input(cursor)
        return True

    def _handle_tab_key(self, event: QEvent) -> bool:
        cursor = self._textCursor()
        if cursor.hasSelection():
            self._setTextCursor(self._indent_selection(cursor))
        else:
            # add spaces until next tabstop boundary:
            tab = self._tab_chars
            buf = self._get_line_until_cursor()
            num = len(tab) - len(buf) % len(tab)
            self.insert_input_text(tab[:num])
        event.accept()
        return True

    def _handle_backtab_key(self, event: QEvent) -> bool:
        self._setTextCursor(self._indent_selection(self._textCursor(), False))
        return True

    def _indent_selection(
        self, cursor: QTextCursor, indent: bool = True
    ) -> QTextCursor:
        buf = self.input_buffer()
        tab = self._tab_chars
        pos0 = cursor.selectionStart() - self._prompt_pos
        pos1 = cursor.selectionEnd() - self._prompt_pos
        line0 = buf[:pos0].count("\n")
        line1 = buf[:pos1].count("\n")
        lines = buf.split("\n")
        for i in range(line0, line1 + 1):
            # Although it at first seemed appealing to me to indent to the
            # next tab boundary, this leads to losing relative sub-tab
            # indentations and is therefore not desirable. We should therefore
            # always indent by a full tab:
            line = lines[i]
            if indent:
                lines[i] = tab + line
            else:
                # Only unindent if line has leading whitespace
                if line and line[0].isspace():
                    # Remove up to one tab width of leading whitespace
                    stripped = line.lstrip()
                    removed = len(line) - len(stripped)
                    keep = max(0, removed - len(tab))
                    lines[i] = (keep * " ") + stripped
                # Line has no indentation, leave it unchanged
            num = len(lines[i]) - len(line)
            pos0 += num if i == line0 else 0
            pos1 += num
        self.clear_input_buffer()
        self.insert_input_text("\n".join(lines))
        cursor.setPosition(self._prompt_pos + pos0)
        cursor.setPosition(self._prompt_pos + pos1, QTextCursor.KeepAnchor)
        return cursor

    def _handle_home_key(self, event: QEvent) -> bool:
        select = event.modifiers() & Qt.ShiftModifier
        self._move_cursor(self._prompt_pos, select)
        return True

    def _handle_up_key(self, event: QEvent) -> bool:
        shift = event.modifiers() & Qt.ShiftModifier
        if shift or "\n" in self.input_buffer()[: self.cursor_offset()]:
            self._move_cursor(QTextCursor.Up, select=shift)
        else:
            self.command_history.dec(self.input_buffer())
        return True

    def _handle_down_key(self, event: QEvent) -> bool:
        shift = event.modifiers() & Qt.ShiftModifier
        if shift or "\n" in self.input_buffer()[self.cursor_offset() :]:
            self._move_cursor(QTextCursor.Down, select=shift)
        else:
            self.command_history.inc()
        return True

    def _handle_left_key(self, event: QEvent) -> bool:
        return self.cursor_offset() < 1

    def _handle_d_key(self, event: QEvent) -> bool:
        if event.modifiers() == Qt.ControlModifier and not self.input_buffer():
            if self._ctrl_d_exits:
                self.exit()
            else:
                self._insert_output_text(
                    "\nCan't use CTRL-D to exit, you have to exit the application !\n"
                )
                self._more = False
                self._update_ps(False)
                self._show_ps()
            return True
        return False

    def _handle_c_key(self, event: QEvent) -> bool:
        intercepted = False
        if event.modifiers() == Qt.ControlModifier:
            self._handle_ctrl_c()
            intercepted = True
        elif event.modifiers() == Qt.ControlModifier | Qt.ShiftModifier:
            self.edit.copy()
            intercepted = True
        return intercepted

    def _handle_u_key(self, event: QEvent) -> bool:
        if event.modifiers() == Qt.ControlModifier and self.input_buffer():
            self.clear_input_buffer()
            return True
        return False

    def _handle_v_key(self, event: QEvent) -> bool:
        if (
            event.modifiers() == Qt.ControlModifier
            or event.modifiers() == Qt.ControlModifier | Qt.ShiftModifier
        ):
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData(QClipboard.Clipboard)
            self.insertFromMimeData(mime_data)
            return True
        return False

    def _hide_cursor(self) -> None:
        self.edit.setCursorWidth(0)

    def _show_cursor(self) -> None:
        self.edit.setCursorWidth(1)

    def _move_cursor(
        self, position: Union[int, QTextCursor.MoveOperation], select: bool = False
    ) -> None:
        cursor = self._textCursor()
        mode = QTextCursor.KeepAnchor if select else QTextCursor.MoveAnchor
        if isinstance(position, QTextCursor.MoveOperation):
            cursor.movePosition(position, mode)
        else:
            cursor.setPosition(position, mode)
        self._setTextCursor(cursor)
        self._keep_cursor_in_buffer()

    def _keep_cursor_in_buffer(self) -> None:
        cursor = self._textCursor()
        if cursor.anchor() < self._prompt_pos:
            # Move to end of input buffer
            cursor.movePosition(QTextCursor.End)
        if cursor.position() < self._prompt_pos:
            # Move to end of input buffer
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        self._setTextCursor(cursor)
        self.ensureCursorVisible()

    def _insert_output_text(
        self,
        text: str,
        lf: bool = False,
        keep_buffer: bool = False,
        prompt: str = "",
        is_error: bool = False,
    ) -> None:
        if keep_buffer:
            self._copy_buffer = self.input_buffer()

        cursor = self._textCursor()
        cursor.movePosition(QTextCursor.End)

        # Insert plain text line by line
        # Only mark non-empty lines (empty lines are for spacing/input)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                cursor.insertText("\n")
            cursor.insertText(line)
            # Mark this block appropriately (only if has content)
            if line:
                block = cursor.block()
                if is_error:
                    block.setUserData(ErrorHighlightData())
                else:
                    block.setUserData(NoHighlightData())

        self._prompt_pos = cursor.position()
        self.ensureCursorVisible()

        self._insert_prompt_text(prompt + "\n" * text.count("\n"), is_output=True)
        self._output_inserted = True
        if lf:
            self.process_input("")

    def _update_prompt_pos(self) -> None:
        cursor = self._textCursor()
        cursor.movePosition(QTextCursor.End)
        self._prompt_pos = cursor.position()
        self._output_inserted = self._more

    def _show_welcome_message(self) -> None:
        """Display the welcome message with plain text formatting.

        Marks each line/block of the welcome message to prevent syntax
        highlighting by using NoHighlightData user data.
        """
        if not self._welcome_message:
            return

        # Clear the current prompt that was shown during init
        self.edit.clear()
        self._prompt_doc = [("", False)]
        self._prompt_pos = 0
        self._output_inserted = False

        cursor = self._textCursor()
        cursor.movePosition(QTextCursor.End)

        # Insert the welcome message line by line, marking each block
        # to prevent syntax highlighting
        lines = self._welcome_message.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                cursor.insertText("\n")
            cursor.insertText(line)
            # Mark this block to not be highlighted
            block = cursor.block()
            block.setUserData(NoHighlightData())

        # Add final newline if message doesn't end with one
        if not self._welcome_message.endswith("\n"):
            cursor.insertText("\n")
            block = cursor.block()
            block.setUserData(NoHighlightData())

        self._prompt_pos = cursor.position()

        # Update prompt area for the welcome message lines
        # Insert empty strings for each line of the welcome message
        newline_count = self._welcome_message.count("\n")
        if not self._welcome_message.endswith("\n"):
            newline_count += 1
        self._insert_prompt_text("\n" * newline_count, is_output=False)

        self._output_inserted = True

        # Now show the first prompt
        self._show_ps()

    @staticmethod
    def _selected_text(cursor: QTextCursor) -> str:
        """Get sanitized selectedText() from a cursor.

        On a multi-line command, Qt includes a paragraph separator
        character (U+2029) instead of a newline. This method replaces
        it with a proper newline.

        Args:
            cursor: QTextCursor to get selected text from.

        Returns:
            Selected text with paragraph separators replaced by newlines.
        """
        # On a multi-line command, Qt will include this 'paragraph separator'
        # character instead of a newline (#109):
        return cursor.selectedText().replace("\u2029", "\n")

    def input_buffer(self) -> str:
        """Retrieve current input buffer in string form.

        Returns:
            String containing all text entered after the last prompt.
        """
        # Use cursor selection to properly handle multi-byte
        # characters like emojis
        cursor = QTextCursor(self.edit.document())
        cursor.setPosition(self._prompt_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        return self._selected_text(cursor)

    def cursor_offset(self) -> int:
        """Get current cursor index within input buffer.

        Returns:
            Integer offset of cursor position from start of input buffer.
        """
        # Extract actual text to get proper string index for multi-byte characters
        cursor = QTextCursor(self.edit.document())
        cursor.setPosition(self._prompt_pos)
        cursor.setPosition(self._textCursor().position(), QTextCursor.KeepAnchor)
        selected_text = self._selected_text(cursor)
        return len(selected_text)

    def _get_line_until_cursor(self) -> str:
        """Get current line of input buffer up to cursor position.

        Returns:
            String containing text from line start to cursor.
        """
        return self.input_buffer()[: self.cursor_offset()].rsplit("\n", 1)[-1]

    def _get_line_after_cursor(self) -> str:
        """Get current line of input buffer after cursor position.

        Returns:
            String containing text from cursor to line end.
        """
        return self.input_buffer()[self.cursor_offset() :].split("\n", 1)[0]

    def clear_input_buffer(self) -> None:
        """Clear the current input buffer."""
        cursor = self._textCursor()
        cursor.setPosition(self._prompt_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        self._remove_selected_input(cursor)
        self._setTextCursor(cursor)

    def insert_input_text(self, text: str, show_ps: bool = True) -> None:
        """Insert text into the input buffer.

        Args:
            text: Text string to insert at cursor position.
            show_ps: If True, show continuation prompts for multi-line input.
                Defaults to True.
        """
        self._keep_cursor_in_buffer()
        self.ensureCursorVisible()

        self._remove_selected_input(self._textCursor())
        self._textCursor().insertText(text)

        if show_ps and "\n" in text:
            self._update_ps(True)
            for _ in range(text.count("\n")):
                # NOTE: need to insert in two steps, because this internally
                # uses setAlignment, which affects only the first line:
                self._insert_prompt_text("\n", is_output=False)
                self._insert_prompt_text(self._ps, is_output=False)
        elif "\n" in text:
            self._insert_prompt_text("\n" * text.count("\n"), is_output=False)

    def process_input(self, source: str) -> None:
        """Handle and execute a source snippet confirmed by the user.

        Processes magic commands (starting with %), shell commands (if enabled),
        or Python code. Updates command history and prompts accordingly.

        Args:
            source: Source code string to process and execute.
        """
        self._last_input = source

        SPECIAL_COMMANDS = {"%": self._run_magic_command, "!": self._run_system_command}
        s = source.strip()

        if len(s) > 0 and s[0] in SPECIAL_COMMANDS:
            SPECIAL_COMMANDS[s[0]](s[1:])
            self._more = False
            if self._last_input:
                # Store command and output for special commands
                output_text = "".join(self._current_command_output)
                self._command_outputs.append((self._last_input, output_text, False))
                self._current_command_output = []
                self._current_line += 1
            self._show_cursor()
            self._update_ps(self._more)
            self.command_history.add(source)
            self._update_prompt_pos()
            self._show_ps()
        else:
            self._more = self._run_source(source)
            self._update_ps(self._more)
            if self._more:
                self._show_ps()
                self._show_cursor()
            else:
                self.command_history.add(source)
                self._update_prompt_pos()

    def _run_system_command(self, command: str) -> None:
        """Execute a system command and display its output.

        Args:
            command: Shell command string to execute.
        """
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            # Display output with OUT prompt
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += result.stderr
            if result.returncode != 0:
                output += f"[Exit code: {result.returncode}]\n"

            if output:
                # Capture output for export
                self._current_command_output.append(output)
                # Highlight as error if command failed
                self._insert_output_text(
                    output, prompt=self.out_prompt(), is_error=(result.returncode != 0)
                )
                self._insert_output_text("\n")
        except subprocess.TimeoutExpired:
            error_msg = "[Command timed out]\n"
            self._current_command_output.append(error_msg)
            self._insert_output_text(error_msg, prompt=self.out_prompt(), is_error=True)
            self._insert_output_text("\n")
        except Exception as e:
            error_msg = f"[Error: {str(e)}]\n"
            self._current_command_output.append(error_msg)
            self._insert_output_text(error_msg, prompt=self.out_prompt(), is_error=True)
            self._insert_output_text("\n")

    def _run_magic_command(self, command: str) -> None:
        """Execute a magic command and display its output."""

        parts = command.split(None, 1)
        magic = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        try:
            output = self.magic.run(magic, args)
            if output:
                # Capture output for export
                self._current_command_output.append(output)
                self._insert_output_text(output, prompt=self.out_prompt())
                self._insert_output_text("\n")

        except Exception as e:
            error_msg = f"Error executing magic command: {str(e)}\n"
            self._current_command_output.append(error_msg)
            self._insert_output_text(error_msg)

    def _handle_ctrl_c(self) -> None:
        """Copy text if selected, else inject keyboard interrupt if executing,
        else cancel the current prompt."""
        # If text is selected, copy it instead of interrupting
        if self._textCursor().hasSelection():
            self.edit.copy()
            return

        # Use the interpreter's thread-safe try_interrupt method to avoid
        # race condition between checking execution state and canceling
        if self._executing():
            self._cancel()
        else:
            self._last_input = ""
            self.stdout.write("^C\n")
            self._output_inserted = False
            self._more = False
            self._update_ps(self._more)
            self._show_ps()

    def _stdout_data_handler(self, data: str) -> None:
        # Capture output for export
        self._current_command_output.append(data)

        self._insert_output_text(data, is_error=self._current_output_is_error)

        if len(self._copy_buffer) > 0:
            self.insert_input_text(self._copy_buffer)
            self._copy_buffer = ""

    def _insert_prompt_text(self, text: str, is_output: bool = False) -> None:
        lines = text.split("\n")
        # Update last entry by appending text
        last_text, last_is_output = self._prompt_doc[-1]
        new_is_output = is_output if lines[0] else last_is_output
        self._prompt_doc[-1] = (last_text + lines[0], new_is_output)
        # Add new entries for additional lines
        self._prompt_doc += [(line, is_output) for line in lines[1:]]
        # Adjust width based on text content
        for line_text, _ in self._prompt_doc[-len(lines) :]:
            self.pbar.adjust_width(line_text)

    def _get_prompt_text(self, line_number: int) -> tuple[str, bool]:
        """Get prompt text and type for a given line number.

        Returns:
            tuple: (text, is_output) where is_output is True for output prompts
        """
        if line_number < len(self._prompt_doc):
            return self._prompt_doc[line_number]
        return ("", False)

    def _remove_selected_input(self, cursor: QTextCursor) -> None:
        if not cursor.hasSelection():
            return

        num_lines = self._selected_text(cursor).count("\n")
        cursor.removeSelectedText()

        if num_lines > 0:
            block = cursor.blockNumber() + 1
            del self._prompt_doc[block : block + num_lines]

    def closeEvent(self, event: QEvent) -> None:
        """Exit interpreter when we're closing."""
        self.exit()
        event.accept()

    def _close(self) -> None:
        if self.window().isVisible():
            self.window().close()

    def set_tab(self, chars: str) -> None:
        """Set the tab character string.

        Args:
            chars: String to use for tab indentation.
        """
        self._tab_chars = chars

    def ctrl_d_exits_console(self, b: bool) -> None:
        """Set whether Ctrl+D exits the console.

        Args:
            b: True to enable Ctrl+D exit, False to disable.
        """
        self._ctrl_d_exits = b

    def clear(self, show_prompt: bool = False) -> None:
        """Clear the console display.

        Args:
            show_prompt: If True, display the prompt after clearing. Set to False
                (default) when called programmatically or from magic commands where
                prompt is shown by caller. Set to True for direct UI actions like
                right-click menu.
        """
        self._prompt_doc = [("", False)]
        self._prompt_pos = 0
        self._output_inserted = False
        self._more = False
        # When show_prompt=True (e.g., right-click),
        # set to 0 and show prompt immediately
        # When show_prompt=False (e.g., %clear magic or clear()),
        # set to -1 so it becomes 0 after increment
        self._current_line = 0 if show_prompt else -1
        self._ps = self.in_prompt()
        self.edit.clear()
        # Clear output tracking
        self._command_outputs = []
        self._current_command_output = []
        # Show the prompt after clearing if requested
        if show_prompt:
            self._show_ps()

    # Abstract

    @abstractmethod
    def exit(self) -> None:
        """Exit the console. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def _executing(self) -> bool:
        """Check if code is currently executing. Must be implemented by subclasses.

        Returns:
            True if executing, False otherwise.
        """
        pass

    @abstractmethod
    def _cancel(self) -> None:
        """Cancel current execution. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def _run_source(self, source: str) -> bool:
        """Run source code. Must be implemented by subclasses.

        Args:
            source: Source code string to run.
        """
        pass

    @abstractmethod
    def get_completions(self, line: str) -> list[str]:
        """Get code completions. Must be implemented by subclasses.

        Args:
            line: Line of code to get completions for.

        Returns:
            List of completion strings.
        """
        return ["No completion support available"]


class Thread(QThread):
    """Thread that runs a Qt event loop.

    Exposes the thread ID as the `ident` attribute and allows
    injecting exceptions to interrupt execution.
    """

    ident: Optional[int]

    def __init__(self, parent: Optional[QThread] = None) -> None:
        """Initialize and start the thread.

        Args:
            parent: Parent QObject. Defaults to None.
        """
        super().__init__(parent)
        self.ready = threading.Event()
        self.start()
        self.ready.wait()

    def run(self) -> None:
        """Run the Qt event dispatcher within the thread."""
        self.ident = threading.current_thread().ident
        self.ready.set()
        self.exec_()

    def inject_exception(self, value: type) -> None:
        """Raise an exception in the thread to stop execution.

        Injects the exception into the remote thread. The exception is raised
        once the thread executes any Python bytecode.

        Args:
            value: Exception class or instance to raise in the thread.
        """
        if self.ident != threading.current_thread().ident:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(self.ident), ctypes.py_object(value)
            )


class PythonConsole(BaseConsole):
    """Interactive Python console widget.

    Provides a fully functional Python console with syntax highlighting,
    auto-completion using Jedi, command history, and magic commands.
    Code can be executed in the main thread or in a separate thread.
    """

    def __init__(
        self,
        parent: Optional[QFrame] = None,
        locals: Optional[dict[str, Any]] = None,
        inprompt: Optional[str] = None,
        outprompt: Optional[str] = None,
        welcome_message: Optional[str] = None,
        pygments_style: Optional[str] = None,
        preamble: Optional[list[str]] = None,
    ) -> None:
        """Initialize the Python console.

        Args:
            parent: Parent widget. Defaults to None.
            locals: Dictionary of local variables for the interpreter namespace.
                Defaults to None.
            inprompt: Input prompt template. Defaults to None.
            outprompt: Output prompt template. Defaults to None.
            welcome_message: Welcome message to display at startup.
                Defaults to None.
            pygments_style: Name of Pygments style (e.g., 'monokai').
                If None, uses 'default' style. Defaults to None.
            preamble: Optional list of lines to add at the top of exported
                scripts/notebooks (e.g., imports). Defaults to None.
        """
        super().__init__(
            parent,
            inprompt=inprompt,
            outprompt=outprompt,
            welcome_message=welcome_message,
            pygments_style=pygments_style,
            preamble=preamble,
        )

        # Display welcome message before creating highlighter
        # to prevent syntax highlighting of the message
        self._show_welcome_message()

        # Use default Pygments style if none specified
        if pygments_style is None:
            pygments_style = "default"

        self.highlighter = PythonHighlighter(
            self.edit.document(), pygments_style=pygments_style
        )
        self.interpreter = PythonInterpreter(self.stdin, self.stdout, locals=locals)
        self.interpreter.done_signal.connect(self._finish_command)
        self.interpreter.exit_signal.connect(self.exit)
        self.interpreter.error_signal.connect(self._error_started)
        self._thread: Optional[Thread] = None

        # Apply the background color from the Pygments style
        self.set_pygments_style(pygments_style)

    def set_pygments_style(self, style_name: str) -> None:
        """Change the Pygments color scheme for both code and prompts.

        Also updates the console background color to match the style's
        background_color attribute if available.

        Args:
            style_name: Name of Pygments style (e.g., 'monokai', 'vim')
        """
        # Update code highlighter
        self.highlighter.updateStyle(style_name)
        # Update prompt highlighter
        self.pbar.highlighter.updateStyle(style_name)

        # Get the background color and default text color from the Pygments style
        try:
            from pygments.token import Token

            style = get_style_by_name(style_name)

            # Get background color
            bg_color = None
            if hasattr(style, "background_color") and style.background_color:
                bg_color = style.background_color

            # Try to get default text color from Token or Token.Text
            fg_color = None
            if Token in style.styles and style.styles[Token]:
                # Extract color from style string
                # (format: "#rrggbb" or "#rrggbb bg:...")
                style_str = style.styles[Token]
                if style_str and style_str.startswith("#"):
                    fg_color = style_str.split()[0]
            elif Token.Text in style.styles and style.styles[Token.Text]:
                style_str = style.styles[Token.Text]
                if style_str and style_str.startswith("#"):
                    fg_color = style_str.split()[0]

            # If no explicit text color, derive from background brightness
            if not fg_color and bg_color:
                # Calculate brightness from hex color
                rgb = QColor(bg_color)
                # Use perceived brightness: https://www.w3.org/TR/AERT/#color-contrast
                brightness = (
                    rgb.red() * 299 + rgb.green() * 587 + rgb.blue() * 114
                ) / 1000
                # If background is light (brightness > 128),
                # use dark text; else use light text
                fg_color = "#000000" if brightness > 128 else "#ffffff"

            # Apply colors to the edit widget using stylesheet
            if bg_color and fg_color:
                stylesheet = (
                    f"QPlainTextEdit {{ "
                    f"background-color: {bg_color}; "
                    f"color: {fg_color}; }}"
                )
                self.edit.setStyleSheet(stylesheet)
            elif bg_color:
                self.edit.setStyleSheet(
                    f"QPlainTextEdit {{ background-color: {bg_color}; }}"
                )
        except Exception as e:
            print(f"Error applying colors for style '{style_name}': {e}")

        # Force repaint of prompt area
        self.pbar.update()

    def clear(self, show_prompt: bool = False) -> None:
        """Clear the console display and reset syntax highlighting cache.

        Args:
            show_prompt: If True, display the prompt after clearing. Set to False
                (default) when called programmatically or from magic commands where
                prompt is shown by caller. Set to True for direct UI actions like
                right-click menu.
        """
        super().clear(show_prompt=show_prompt)
        # Clear the highlighter's cache to prevent highlighting sync issues
        if hasattr(self, "highlighter"):
            self.highlighter._cached_doc_text = None
            self.highlighter._line_formats = {}

    def _executing(self):
        """Check if the interpreter is currently executing code.

        Returns:
            True if code is executing, False otherwise.
        """
        return self.interpreter.executing()

    def _cancel(self):
        """Cancel current code execution by injecting KeyboardInterrupt.

        Note: Only works with eval_in_thread(). With eval_queued(), the main
        thread is blocked and cannot process keyboard events during execution.
        """
        if self._thread:
            self.interpreter.try_interrupt(self._thread)
            # wake up thread in case it is currently waiting on input:
            self.stdin.flush()

    def _run_source(self, source: str) -> bool:
        """Run Python source code in the interpreter.

        Args:
            source: Python source code string to execute.

        Returns:
            True if more input is needed (incomplete statement), False otherwise.
        """
        return self.interpreter.runsource(source, symbol="multi")

    def exit(self) -> None:
        """Exit the console and cleanup resources.

        Stops execution thread if running and closes the console.
        """
        if self._thread:
            self._thread.exit()
            self._thread.wait()
            self._thread = None
        self._close()

    def get_completions(self, line: str) -> list[str]:
        """Get code completions using Jedi.

        Args:
            line: Line of code to get completions for.

        Returns:
            List of completion name strings.
        """
        script = Interpreter(line, [self.interpreter.locals])

        comps = script.complete()

        return [comp.name for comp in comps]

    def push_local_ns(self, name: str, value: Any) -> None:
        """Set a variable in the interpreter's local namespace.

        Args:
            name: Variable name string.
            value: Value to assign to the variable.
        """
        self.interpreter.locals[name] = value

    def eval_in_thread(self) -> Thread:
        """Start a thread in which code snippets will be executed.

        Creates and starts an execution thread that runs code in the background.
        This allows the Qt event loop to continue processing UI events, including
        keyboard interrupts (Ctrl+C/Cmd+C) during code execution.

        Returns:
            Thread object that will execute code snippets.
        """
        self._thread = Thread()
        self.interpreter.moveToThread(self._thread)
        self.interpreter.exec_signal.connect(self.interpreter.exec_, QueuedConnection)
        return self._thread

    def eval_queued(self) -> Any:
        """Execute code snippets in later mainloop iterations in main thread.

        Sets up queued connections to execute code in the main event loop.

        WARNING: Code executes in the main Qt thread, blocking the event loop.
        This means:
        - UI will freeze during long-running code
        - Keyboard events (including Ctrl+C) cannot be processed during execution
        - Interruption via Ctrl+C is NOT possible

        Use eval_in_thread() instead if you need to interrupt long-running code.

        Returns:
            The signal-slot connection.
        """
        return self.interpreter.exec_signal.connect(
            self.interpreter.exec_, QueuedConnection
        )

    def eval_executor(self, spawn: Callable[[Callable, str], Any]) -> Any:
        """Execute code using a custom executor function.

        Sets up code execution using the given executor function
        (e.g., gevent.spawn for async execution).

        Args:
            spawn: Executor function that takes (callable, args) and spawns execution.

        Returns:
            The signal-slot connection.
        """
        return self.interpreter.exec_signal.connect(
            lambda line: spawn(self.interpreter.exec_, line)
        )

    def export_as_script(
        self, filepath: Optional[str] = None, strip_prompts: bool = True
    ) -> bool:
        """Export console session as a Python script or Jupyter notebook.

        Opens a file dialog to select save location if filepath is not provided.
        If the file extension is .ipynb, exports as a Jupyter notebook with
        code cells and captured outputs. Otherwise, exports as a Python script.
        Magic commands (%) and shell commands (!) are exported as comments in
        .py files, or as code cells with magic syntax in .ipynb files.

        Args:
            filepath: Optional path to save the script. If None, opens a file dialog.
            strip_prompts: If True, removes empty lines and cleans up the output.
                Defaults to True.

        Returns:
            True if export was successful, False if cancelled or failed.
        """
        return export_session(
            commands=self.command_history._cmd_history,
            command_outputs=self._command_outputs,
            parent=self,
            filepath=filepath,
            strip_prompts=strip_prompts,
            preamble=self._preamble,
        )


class InputArea(QPlainTextEdit):
    """Text edit widget for the console's input/output area.

    Delegates paste operations to the parent console widget.
    """

    def insertFromMimeData(self, mime_data: Any) -> None:
        """Insert clipboard data by delegating to parent console.

        Args:
            mime_data: QMimeData containing clipboard content.
        """
        return self.parent().insertFromMimeData(mime_data)

    def mousePressEvent(self, event):
        """Ensure widget gets focus when clicked."""
        self.setFocus(Qt.MouseFocusReason)
        super().mousePressEvent(event)

    def _toggle_word_wrap(self) -> None:
        """Toggle word wrap mode between NoWrap and WidgetWidth."""
        if self.lineWrapMode() == QPlainTextEdit.NoWrap:
            self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        else:
            self.setLineWrapMode(QPlainTextEdit.NoWrap)

    def contextMenuEvent(self, event: Any) -> None:
        """Show custom context menu with copy, paste, and select all.

        Args:
            event: QContextMenuEvent containing menu request details.
        """
        menu = self.createStandardContextMenu()

        # Find and enable the paste action (disabled in read-only mode)
        paste_action = None
        for action in menu.actions():
            # The paste action exists but is disabled in read-only mode
            if "paste" in action.text().lower():
                paste_action = action
                break

        if paste_action:
            # Enable it and reconnect to our custom handler
            # Icon is already set from the standard menu
            paste_action.setEnabled(True)
            # Disconnect default handler and connect ours
            paste_action.triggered.disconnect()
            paste_action.triggered.connect(
                lambda: self.parent().insertFromMimeData(
                    QApplication.clipboard().mimeData(QClipboard.Clipboard)
                )
            )
        else:
            # Fallback: create paste action with system icon

            # Find position after copy
            insert_pos = 0
            for i, action in enumerate(menu.actions()):
                if "copy" in action.text().lower():
                    insert_pos = i + 1
                    break

            paste_action = menu.addAction("Paste")
            paste_action.setShortcut("Ctrl+V")

            # Try to get icon from a temporary standard menu
            # This ensures we use the same icons as the system
            temp_widget = QPlainTextEdit()
            temp_menu = temp_widget.createStandardContextMenu()
            for temp_action in temp_menu.actions():
                if "paste" in temp_action.text().lower():
                    paste_action.setIcon(temp_action.icon())
                    break
            temp_menu.deleteLater()
            temp_widget.deleteLater()

            paste_action.triggered.connect(
                lambda: self.parent().insertFromMimeData(
                    QApplication.clipboard().mimeData(QClipboard.Clipboard)
                )
            )

            # Move to correct position
            if insert_pos < len(menu.actions()) - 1:
                menu.removeAction(paste_action)
                menu.insertAction(menu.actions()[insert_pos], paste_action)

        # Add separator and additional actions
        menu.addSeparator()

        # Add Clear Console action
        clear_action = menu.addAction("Clear Console")
        clear_action.triggered.connect(lambda: self.parent().clear(show_prompt=True))

        # Add Export Session action (only for PythonConsole)
        console = self.parent()
        if hasattr(console, "export_as_script"):
            export_action = menu.addAction("Export Session...")
            export_action.triggered.connect(lambda: console.export_as_script())

        # Add Toggle Word Wrap action
        menu.addSeparator()
        wrap_action = menu.addAction("Toggle Word Wrap")
        wrap_action.setCheckable(True)
        wrap_action.setChecked(self.lineWrapMode() == QPlainTextEdit.WidgetWidth)
        wrap_action.triggered.connect(self._toggle_word_wrap)

        menu.exec_(event.globalPos())
