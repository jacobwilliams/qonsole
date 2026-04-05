#! /usr/bin/env python

import sys

from qtpy.QtWidgets import QApplication

from qonsole.console import PythonConsole
from qonsole.highlighter import format


def greet():
    print("hello world")


if __name__ == "__main__":
    app = QApplication([])

    console = PythonConsole(formats={"keyword": format("darkBlue", "bold")})
    console.push_local_ns("greet", greet)
    console.show()

    console.eval_queued()

    sys.exit(app.exec_())
