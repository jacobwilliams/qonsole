"""Magic commands for the console.

Provides IPython-like magic commands such as %pwd, %cd, %ls, %who, %whos,
%timeit, %run, %clear, and %help.
"""

import os
import platform
import subprocess
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .console import PythonConsole

LS_CMD: str = "dir" if platform.system() == "Windows" else "ls"


class MagicCmds:
    """Manager for magic commands in the console.

    Provides IPython-like magic commands that start with % for common
    operations like file system navigation, variable inspection, and timing.
    """

    def __init__(self, parent: "PythonConsole") -> None:
        """Initialize the magic commands manager.

        Args:
            parent: Parent console widget (an instance of PythonConsole).
        """
        self.parent = parent

        self.MAGIC_COMMANDS: dict[str, Callable[[Optional[str]], str]] = {
            "pwd": self._PWD,
            "cd": self._CD,
            "ls": self._LS,
            "help": self._HELP,
            "clear": self._CLEAR,
            "who": self._WHO,
            "whos": self._WHOS,
            "timeit": self._TIMEIT,
            "run": self._RUN,
        }  # magic command name (without %) -> function(args) mapping

    def _PWD(self, args: Optional[str] = None) -> str:
        """Return current working directory.

        Args:
            args: Unused, for consistency with other magic commands.

        Returns:
            Current working directory path with newline.
        """
        return os.getcwd() + "\n"

    def _CD(self, args: Optional[str] = None) -> str:
        """Change current working directory.

        Args:
            args: Optional target directory path.
                If None, stays in current directory.

        Returns:
            New current working directory path with newline.
        """
        if args:
            os.chdir(os.path.expanduser(args))
        return os.getcwd() + "\n"

    def _LS(self, args: Optional[str] = None) -> str:
        """List directory contents.

        Args:
            args: Optional arguments to pass to ls/dir command (e.g., "-l", "-a").

        Returns:
            Directory listing output from the system command.
        """
        result = subprocess.run(
            f"{LS_CMD} {args}" if args else LS_CMD,
            shell=True,
            capture_output=True,
            text=True,
        )
        return result.stdout if result.stdout else result.stderr

    def _CLEAR(self, args: Optional[str] = None) -> str:
        """Clear the console display.

        Args:
            args: Unused, for consistency with other magic commands.

        Returns:
            Empty string.
        """
        self.parent.clear()
        return ""

    def _WHO(self, args: Optional[str] = None) -> str:
        """List variable names in the current namespace.

        Args:
            args: Unused, for consistency with other magic commands.

        Returns:
            Space-separated list of non-private variable names,
            or "No variables".
        """
        vars_list = [
            name for name in self.parent.interpreter.locals if not name.startswith("_")
        ]
        return "  ".join(sorted(vars_list)) + "\n" if vars_list else "No variables\n"

    def _WHOS(self, args: Optional[str] = None) -> str:
        """Display detailed variable information.

        Shows variable name, type, and a truncated representation for each
        non-private variable in the current namespace.

        Args:
            args: Unused, for consistency with other magic commands.

        Returns:
            Formatted table of variable information.
        """
        lines = ["Variable   Type         Data/Info\n"]
        lines.append("-" * 50 + "\n")
        for name in sorted(self.parent.interpreter.locals.keys()):
            if not name.startswith("_"):
                obj = self.parent.interpreter.locals[name]
                obj_type = type(obj).__name__
                try:
                    obj_repr = repr(obj)
                    if len(obj_repr) > 40:
                        obj_repr = obj_repr[:37] + "..."
                except Exception:
                    obj_repr = "<repr failed>"
                lines.append(f"{name:<10} {obj_type:<12} {obj_repr}\n")
        return "".join(lines) if len(lines) > 2 else "No variables\n"

    def _TIMEIT(self, args: Optional[str] = None) -> str:
        """Time the execution of a Python statement.

        Runs the statement multiple times and reports the average time per loop.

        Args:
            args: Python statement to time.

        Returns:
            Formatted timing results or error message.
        """
        if not args:
            return "Usage: %timeit <statement>\n"
        import timeit

        try:
            num = 10000  # number of executions to average over
            per_loop = (
                timeit.Timer(args, globals=self.parent.interpreter.locals).timeit(num)
                / num
            )
            for threshold, scale, unit in [
                (1e-6, 1e9, "ns"),
                (1e-3, 1e6, "µs"),
                (1, 1e3, "ms"),
            ]:
                if per_loop < threshold:
                    return (
                        f"{per_loop * scale:.1f} {unit} ± per loop "
                        f"(mean of {num} runs)\n"
                    )
            return f"{per_loop:.3f} s ± per loop (mean of {num} runs)\n"
        except Exception as e:
            return f"Error timing code: {str(e)}\n"

    def _RUN(self, args: Optional[str]) -> str:
        """Execute a Python script file.

        Runs the specified Python file in the current interpreter namespace.

        Args:
            args: Path to the Python script file to execute.

        Returns:
            Empty string on success, or error message on failure.
        """
        if not args:
            return "Usage: %run <script.py>\n"
        import runpy

        try:
            script_path = os.path.expanduser(args.strip())
            runpy.run_path(
                script_path,
                init_globals=self.parent.interpreter.locals,
                run_name="__main__",
            )
            return ""
        except FileNotFoundError:
            return f"File not found: {args}\n"
        except Exception as e:
            return f"Error running script: {str(e)}\n"

    def _HELP(self, args: Optional[str] = None) -> str:
        """Display help message for magic commands.

        Args:
            args: Unused, for consistency with other magic commands.

        Returns:
            List of available magic commands.
        """
        available_cmds = ", ".join(
            [f"%{c}" for c in sorted(self.MAGIC_COMMANDS.keys())]
        )
        return f"Available magic commands: {available_cmds}\n"

    def run(self, cmd: str, args: Optional[str]) -> str:
        """Execute a magic command.

        Args:
            cmd: Magic command name (without the % prefix).
            args: Arguments string to pass to the command.

        Returns:
            Command output string, or error message if command not found.
        """
        if cmd in self.MAGIC_COMMANDS:
            return self.MAGIC_COMMANDS[cmd](args)
        else:
            return f"Unknown magic command: %{cmd}\n" + self._HELP()

    def add_magic_command(
        self, name: str, func: Callable[[Optional[str]], str]
    ) -> None:
        """Add a custom magic command.

        Args:
            name: Name of the magic command (without % prefix).
            func: Callable that takes a single string argument (args) and
                returns a string output.
        """
        self.MAGIC_COMMANDS[name] = func
