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
