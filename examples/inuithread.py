#! /usr/bin/env python

import sys

from qtpy.QtWidgets import QApplication

from qonsole import PythonConsole


def greet():
    print("hello world")


if __name__ == "__main__":
    app = QApplication([])

    console = PythonConsole(pygments_style="monokai")
    console.push_local_ns("greet", greet)
    console.show()

    console.eval_queued()

    sys.exit(app.exec_())
