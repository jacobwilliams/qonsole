qonsole
===========

qonsole is a lightweight python console for Qt applications. It's made to
be easy to embed in other Qt applications and comes with some examples that
show how this can be done. The interpreter can run in a separate thread, in
the UI main thread or in a gevent task.

qonsole is a fork of [pyqtconsole](https://github.com/pyqtconsole/pyqtconsole).

## Simple usage

The following snippet shows how to create a console that will execute user
input in a separate thread. Be aware that long running tasks will still block
the main thread due to the GIL. See the ``examples`` directory for more
examples.

```python
    import sys
    from threading import Thread
    from PyQt5.QtWidgets import QApplication

    from qonsole.console import PythonConsole

    app = QApplication([])
    console = PythonConsole()
    console.show()
    console.eval_in_thread()

    sys.exit(app.exec_())
```

## Embedding

* *Separate thread* - Runs the interpreter in a separate thread, see the
  example threaded.py_. Running the interpreter in a separate thread obviously
  limits the interaction with the Qt application. The parts of Qt that needs
  to be called from the main thread will not work properly, but is excellent
  way for having a 'plain' python console in your Qt app.

* *main thread* - Runs the interpreter in the main thread, see the example
  inuithread.py_. Makes full interaction with Qt possible, lenghty operations
  will of course freeze the UI (as any lenghty operation that is called from
  the main thread). This is a great alternative for people who does not want
  to use the gevent based approach but still wants full interactivity with Qt.

* *gevent* - Runs the interpreter in a gevent task, see the example
  `_gevent.py`_. Allows for full interactivity with Qt without special
  consideration (at least to some extent) for longer running processes. The
  best method if you want to use pyQtgraph, Matplotlib, PyMca or similar.

## Features

### Syntax highlighting

Syntax highlighting is provided by the [https://pygments.org](pygments) library.
Simply pass the Pygments style string to the ``PythonConsole`` constructer like so:

```python
    console = PythonConsole(pygments_style='github-dark')
```

### Clear console

A local method, named `clear()`, is available to clear the input screen and reset the line numbering.
Enable it by pushing the method into the available namespace in the console:

```
   console.interpreter.locals["clear"] = console.clear
```

### Shell commands

Optionally, commands entered in the console that start with a special character (e.g. '!') will be executed as shell commands.
The output of the command will be printed in the console.
For example, on a Linux or macOS system, entering `!ls -l` will list the files in the current directory.
This feature is enabled by default, but can be disabled by setting the ``shell_cmd_prefix=False`` parameter when creating the console.

```python
   console = PythonConsole()
```

```
   IN [0]: !ls -l
   OUT[0]: total 16546
           -rw-r--r-- 1 user user      18741 Fen  6  2026  file1.txt
           -rw-r--r-- 1 user user      18741 Feb  6  2026  file2.txt
```

### Prompt String

By default ``IN [n]:`` and ``OUT [n]:`` are displayed before each input and output line.
You can customize this through constructor arguments:

```python
   # Including the line numbers:
   console = PythonConsole(inprompt="%d >", outprompt="%d <")
   # Or just static:
   console = PythonConsole(inprompt=">>>", outprompt="<<<")
```

## Credits

This module depends on QtPy which provides a compatibility layer for
Qt4 and Qt5. The console is tested under both Qt4 and Qt5.


<!-- .. _threaded.py: https://github.com/jacobwilliams/qonsole/blob/master/examples/threaded.py
.. _inuithread.py: https://github.com/jacobwilliams/qonsole/blob/master/examples/inuithread.py
.. _`_gevent.py`: https://github.com/jacobwilliams/qonsole/blob/master/examples/_gevent.py
.. _QtPy: https://github.com/spyder-ide/qtpy


.. Badges:

.. |PyPi| image::       https://img.shields.io/pypi/v/qonsole.svg
   :target:             https://pypi.org/project/qonsole
   :alt:                Latest Version

.. |Python| image::     https://img.shields.io/pypi/pyversions/qonsole.svg
   :target:             https://pypi.org/project/qonsole#files
   :alt:                Python versions

.. |License| image::    https://img.shields.io/pypi/l/qonsole.svg
   :target:             https://github.com/jacobwilliams/qonsole/blob/master/LICENSE
   :alt:                License: MIT

.. |Tests| image::      https://github.com/jacobwilliams/qonsole/actions/workflows/tests.yml/badge.svg
   :target:             https://github.com/jacobwilliams/qonsole/actions/workflows/tests.yml
   :alt:                Tests status

.. |Conda| image::      https://img.shields.io/conda/vn/conda-forge/qonsole.svg
   :target:             https://anaconda.org/conda-forge/qonsole
   :alt:                Conda-Forge -->
