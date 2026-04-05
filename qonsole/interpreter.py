"""Python interpreter with Qt signal support.

Provides a PythonInterpreter class that extends Python's InteractiveInterpreter
with Qt signals for code execution, completion, and error handling.
"""

import ast
import contextlib
import sys
from code import InteractiveInterpreter
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Optional

from qtpy.QtCore import QObject, Signal, Slot

if TYPE_CHECKING:
    from .stream import Stream


class PythonInterpreter(QObject, InteractiveInterpreter):
    """Interactive Python interpreter with Qt signal integration.

    Extends Python's InteractiveInterpreter to execute code with Qt signals
    for tracking execution state and handling errors.

    Attributes:
        exec_signal: Signal emitted when code is ready to execute.
        done_signal: Signal emitted when execution completes with result.
        exit_signal: Signal emitted when SystemExit is raised.
        error_signal: Signal emitted when error output is about to be written.
    """

    exec_signal = Signal(object)
    done_signal = Signal(object)
    exit_signal = Signal(object)
    error_signal = Signal()  # Emitted when error output is about to be written

    def __init__(
        self,
        stdin: "Stream",
        stdout: "Stream",
        locals: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize the Python interpreter.

        Args:
            stdin: Input stream for reading user input.
            stdout: Output stream for writing results and errors.
            locals: Optional dictionary of local variables. Defaults to None.
        """
        QObject.__init__(self)
        InteractiveInterpreter.__init__(self, locals)
        self.locals["exit"] = Exit()
        self.stdin = stdin
        self.stdout = stdout
        self._executing: bool = False
        self.compile: Callable = partial(compile_multi, self.compile)

    def executing(self) -> bool:
        """Check if code is currently executing.

        Returns:
            True if code is executing, False otherwise.
        """
        return self._executing

    def runcode(self, code: Any) -> None:
        """Execute compiled code by emitting exec_signal.

        Args:
            code: Compiled code object to execute.
        """
        self.exec_signal.emit(code)

    @Slot(object)
    def exec_(self, codes: list[tuple[Any, str]]) -> None:
        """Execute a list of compiled code objects.

        Executes code with redirected I/O and proper exception handling.
        Emits done_signal when complete and exit_signal for SystemExit.

        Args:
            codes: List of tuples (code, mode) where mode is 'eval' or 'exec'.
        """
        self._executing = True
        result: Any = None

        # Redirect IO and disable excepthook, this is the only place were we
        # redirect IO, since we don't how IO is handled within the code we
        # are running. Same thing for the except hook, we don't know what the
        # user are doing in it.
        try:
            with redirected_io(self.stdout):
                for code, mode in codes:
                    if mode == "eval":
                        result = eval(code, self.locals)
                    else:
                        exec(code, self.locals)
        except SystemExit as e:
            self.exit_signal.emit(e)
        except BaseException:
            self.showtraceback()
        finally:
            self._executing = False
            self.done_signal.emit(result)

    def write(self, data: str) -> None:
        """Write data to stdout.

        Args:
            data: String data to write.
        """
        self.stdout.write(data)

    def showtraceback(self) -> None:
        """Display the exception traceback.

        Emits error_signal and writes traceback to stdout. Handles
        KeyboardInterrupt specially as a simple message.
        """
        type_, value, tb = sys.exc_info()
        self.error_signal.emit()  # Signal that error output is coming
        self.stdout.write("\n")

        if type_ is KeyboardInterrupt:
            self.stdout.write("KeyboardInterrupt\n")
        else:
            with disabled_excepthook():
                InteractiveInterpreter.showtraceback(self)

    def showsyntaxerror(self, filename: Optional[str] = None, **kwargs: Any) -> None:
        """Display a syntax error.

        Emits error_signal and writes syntax error to stdout.

        Args:
            filename: Optional filename where the error occurred.
            **kwargs: Additional keyword arguments for compatibility.
        """
        self.error_signal.emit()  # Signal that error output is coming
        self.stdout.write("\n")

        with disabled_excepthook():
            # It seems Python 3.13 requires **kwargs, older versions don't
            InteractiveInterpreter.showsyntaxerror(self, filename, **kwargs)
        self.done_signal.emit(None)


def compile_multi(
    compiler: Callable, source: str, filename: str, symbol: str
) -> Optional[list[tuple[Any, str]]]:
    """Compile source code with support for multiple statements.

    If mode is 'multi', splits code into individual toplevel expressions or
    statements and compiles each separately.

    Args:
        compiler: Compiler function to use for compiling code.
        source: Source code string to compile.
        filename: Filename for error messages.
        symbol: Compilation mode ('single', 'exec', 'eval', or 'multi').

    Returns:
        List of tuples (code, mode) where code is compiled code object and
        mode is 'eval' or 'exec'. Returns None if code is incomplete.
    """
    if symbol != "multi":
        return [(compiler(source, filename, symbol), symbol)]
    # First, check if the source compiles at all. This raises an exception if
    # there is a SyntaxError, or returns None if the code is incomplete:
    if compiler(source, filename, "exec") is None:
        return None
    # Now split into individual 'single' units:
    module = ast.parse(source)
    # When entering a code block, the standard python interpreter waits for an
    # additional empty line to apply the input. We adhere to this convention,
    # checked by `compiler(..., 'single')`:
    if module.body:
        block_lineno = module.body[-1].lineno
        block_source = source[find_nth("\n" + source, "\n", block_lineno) :]
        if compiler(block_source, filename, "single") is None:
            return None
    return [compile_single_node(node, filename) for node in module.body]


def compile_single_node(node: ast.AST, filename: str) -> tuple[Any, str]:
    """Compile a single AST node (expression or statement).

    Args:
        node: AST node to compile.
        filename: Filename for error messages.

    Returns:
        Tuple of (compiled_code, mode) where mode is 'eval' or 'exec'.
    """
    mode = "eval" if isinstance(node, ast.Expr) else "exec"
    if mode == "eval":
        root = ast.Expression(node.value)
    else:
        root = ast.Module([node], type_ignores=[])
    return (compile(root, filename, mode), mode)


def find_nth(string: str, char: str, n: int) -> int:
    """Find the n-th occurrence of a character within a string.

    Args:
        string: String to search in.
        char: Character to find.
        n: Which occurrence to find (1-indexed).

    Returns:
        Index of the n-th occurrence of char in string.
    """
    return [i for i, c in enumerate(string) if c == char][n - 1]


@contextlib.contextmanager
def disabled_excepthook():
    """Context manager to temporarily disable the exception hook.

    Yields:
        None
    """
    old_excepthook = sys.excepthook
    sys.excepthook = sys.__excepthook__

    try:
        yield
    finally:
        # If the code we did run did change sys.excepthook, we leave it
        # unchanged. Otherwise, we reset it.
        if sys.excepthook is sys.__excepthook__:
            sys.excepthook = old_excepthook


@contextlib.contextmanager
def redirected_io(stdout: "Stream"):
    """Context manager to redirect stdout and stderr.

    Args:
        stdout: Stream to redirect standard output and error to.

    Yields:
        None
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = stdout
    sys.stderr = stdout
    try:
        yield
    finally:
        if sys.stdout is stdout:
            sys.stdout = old_stdout
        if sys.stderr is stdout:
            sys.stderr = old_stderr


# We use a custom exit function to avoid issues with environments such as
# spyder, where `builtins.exit` is not available, see #26:
class Exit:
    """Custom exit function for the console.

    Provides a user-friendly exit interface that works in all environments.
    """

    def __repr__(self) -> str:
        """Return usage message.

        Returns:
            String instructing user how to exit the console.
        """
        return "Type exit() to exit this console."

    def __call__(self, *args: Any) -> None:
        """Exit the console when called.

        Args:
            *args: Optional exit code or message.

        Raises:
            SystemExit: Always raised to exit the console.
        """
        raise SystemExit(*args)
