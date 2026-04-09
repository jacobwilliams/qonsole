"""[qonsole](https://github.com/jacobwilliams/qonsole) - Lightweight python console for Qt applications.

This module provides an embeddable Python console widget for Qt applications.
It supports syntax highlighting, command history, magic commands,
and autocompletion.

.. include:: ../README.md
   :start-line: 5
"""

__version__ = "2.0.2"
__description__ = "Lightweight python console, easy to embed into Qt applications"


from .console import PythonConsole as PythonConsole
