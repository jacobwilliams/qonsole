#! /usr/bin/env python

import sys

from qtpy.QtWidgets import QApplication

from qonsole.console import PythonConsole

welcome_msg = """Python Console v1.0
Commands starting with ! are executed as shell commands
"""

welcome_msg = """Python Console v1.0
Commands starting with ! are executed as shell commands
"""


def greet():
    print("hello world")


def version(args=None):
    """example of a custom magic command"""
    import qonsole

    return str(qonsole.__version__)


if __name__ == "__main__":
    app = QApplication([])

    console = PythonConsole(shell_cmd_prefix=True, welcome_message=welcome_msg)
    console.push_local_ns("greet", greet)
    console.interpreter.locals["clear"] = console.clear

    # add a custom magic command:
    console.add_magic_command("version", version)

    console.show()
    console.eval_in_thread()
    sys.exit(app.exec_())
