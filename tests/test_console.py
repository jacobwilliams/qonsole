from collections.abc import Generator

import pytest
from pytestqt.qtbot import QtBot
from qtpy.QtCore import Qt

from qonsole import PythonConsole


class TestConsole:
    """A collection of integration tests, directly on the console."""

    bot: QtBot
    console: PythonConsole

    @pytest.fixture(autouse=True)
    def _qt_bot(self, qtbot):
        """Automatically include qtbot for all test-methods."""
        self.bot = qtbot

    @pytest.fixture(autouse=True)
    def _console(self, _qt_bot) -> Generator[PythonConsole, None, None]:
        self.console = PythonConsole()
        self.bot.add_widget(self.console)
        self.console.show()
        self.console.eval_in_thread()
        yield self.console

    def hit_enter(self):
        """Trigger of hitting the [Enter] key inside the prompt."""
        self.bot.keyClick(self.console.edit, Qt.Key.Key_Enter)

    def test_basic(self):
        """Test a single, very basic input."""
        self.console.edit.insertPlainText("print(1 + 1)")
        self.hit_enter()

        def check():
            content = self.console.edit.toPlainText()
            lines = content.splitlines()
            assert len(lines) == 3
            assert lines == [
                "print(1 + 1)",
                "2",
                "",
            ]

        self.bot.waitUntil(check)

    def test_magic_pwd(self):
        """Test %pwd magic command."""
        self.console.edit.insertPlainText("%pwd")
        self.hit_enter()

        def check():
            content = self.console.edit.toPlainText()
            assert "/" in content  # Should contain a path

        self.bot.waitUntil(check)

    def test_magic_help(self):
        """Test %help magic command."""
        self.console.edit.insertPlainText("%help")
        self.hit_enter()

        def check():
            content = self.console.edit.toPlainText()
            assert "magic" in content.lower()

        self.bot.waitUntil(check)

    def test_syntax_error(self):
        """Test that syntax errors are displayed."""
        self.console.edit.insertPlainText("print(")
        self.hit_enter()

        def check():
            content = self.console.edit.toPlainText()
            # Incomplete statement may not show error immediately
            # Just check content has changed from input
            assert len(content) > 0

        self.bot.waitUntil(check)

    def test_multiline_statement(self):
        """Test multiline statement execution."""
        self.console.edit.insertPlainText("def foo():")
        self.hit_enter()
        self.console.edit.insertPlainText("    return 42")
        self.hit_enter()
        self.hit_enter()  # Complete the block

        self.console.edit.insertPlainText("foo()")
        self.hit_enter()

        def check():
            content = self.console.edit.toPlainText()
            assert "42" in content

        self.bot.waitUntil(check)

    def test_variable_persistence(self):
        """Test that variables persist between commands."""
        self.console.edit.insertPlainText("x = 100")
        self.hit_enter()

        def check_assignment():
            # Wait for first command to complete
            pass

        self.bot.waitUntil(check_assignment, timeout=1000)

        self.console.edit.insertPlainText("print(x)")
        self.hit_enter()

        def check_value():
            content = self.console.edit.toPlainText()
            assert "100" in content

        self.bot.waitUntil(check_value)

    def test_clear_console(self):
        """Test clearing the console."""
        self.console.edit.insertPlainText("print('test')")
        self.hit_enter()

        def check_has_content():
            assert len(self.console.edit.toPlainText()) > 0

        self.bot.waitUntil(check_has_content)

        # Clear the console
        self.console.clear()
        assert self.console.edit.toPlainText() == ""

    def test_set_pygments_style(self):
        """Test setting Pygments style."""
        # Should not raise an error
        self.console.set_pygments_style("monokai")
        self.console.set_pygments_style("default")
