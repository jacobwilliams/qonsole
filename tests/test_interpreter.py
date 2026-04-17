"""Test interpreter functionality."""

import pytest

from qonsole.interpreter import PythonInterpreter
from qonsole.stream import Stream


class TestPythonInterpreter:
    """Test Python interpreter wrapper."""

    @pytest.fixture
    def interpreter(self):
        """Create a PythonInterpreter instance."""
        stdin = Stream()
        stdout = Stream()
        interp = PythonInterpreter(stdin, stdout)
        return interp

    def test_initialization(self, interpreter):
        """Test interpreter initializes properly."""
        assert interpreter.locals is not None
        assert "exit" in interpreter.locals

    def test_executing_property(self, interpreter):
        """Test executing property."""
        assert interpreter.executing() is False

    def test_compile_simple_expression(self, interpreter):
        """Test compiling a simple expression."""
        code = interpreter.compile("1 + 1", "<stdin>", "eval")
        assert code is not None

    def test_compile_statement(self, interpreter):
        """Test compiling a statement."""
        code = interpreter.compile("x = 42", "<stdin>", "exec")
        assert code is not None

    def test_locals_namespace(self, interpreter):
        """Test accessing locals namespace."""
        # Manually execute code
        code = compile("y = 100", "<stdin>", "exec")
        exec(code, interpreter.locals)
        assert "y" in interpreter.locals
        assert interpreter.locals["y"] == 100

    def test_showsyntaxerror(self, interpreter):
        """Test showsyntaxerror method emits signals and writes output."""
        # Track signal emissions
        error_signal_emitted = []
        done_signal_emitted = []

        def error_handler():
            error_signal_emitted.append(True)

        def done_handler(result):
            done_signal_emitted.append(result)

        interpreter.error_signal.connect(error_handler)
        interpreter.done_signal.connect(done_handler)

        # Track stdout output
        stdout_output = []

        def stdout_handler(data):
            stdout_output.append(data)

        interpreter.stdout.write_event.connect(stdout_handler)

        # Trigger a syntax error by calling showsyntaxerror
        # This simulates what happens when the interpreter encounters bad syntax
        try:
            compile("def bad syntax(", "<test>", "exec")
        except SyntaxError:
            import sys
            sys.last_type, sys.last_value, sys.last_traceback = sys.exc_info()
            interpreter.showsyntaxerror("<test>")

        # Verify error_signal was emitted
        assert len(error_signal_emitted) == 1

        # Verify done_signal was emitted with None
        assert len(done_signal_emitted) == 1
        assert done_signal_emitted[0] is None

        # Verify output was written to stdout (at least a newline)
        assert len(stdout_output) > 0
        assert any("\n" in output for output in stdout_output)
