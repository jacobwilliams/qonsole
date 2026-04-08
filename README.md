<h1 align="center">
   <img src="https://raw.githubusercontent.com/jacobwilliams/qonsole/master/media/qonsole.png" width=800">
</h1>

<!-- Badges -->
<p align="left">
  <!-- Python version badge -->
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/language-python-blue.svg" alt="Python"></a>
  <!-- PyPI badge -->
  <a href="https://pypi.org/project/qonsole/"><img src="https://img.shields.io/pypi/v/qonsole.svg" alt="PyPI"></a>
  <!-- conda-forge badge -->
  <a href="https://anaconda.org/conda-forge/qonsole"><img src="https://img.shields.io/conda/vn/conda-forge/qonsole.svg" alt="Conda-Forge"></a>
  <!-- GitHub Actions CI badge -->
  <a href="https://github.com/jacobwilliams/qonsole/actions"><img src="https://github.com/jacobwilliams/qonsole/actions/workflows/docs.yml/badge.svg" alt="GitHub CI Status"></a>
  <a href="https://github.com/jacobwilliams/qonsole/actions"><img src="https://github.com/jacobwilliams/qonsole/actions/workflows/publish.yml/badge.svg" alt="GitHub CI Status"></a>
</p>

# qonsole

Qonsole is a lightweight Python console for Qt applications. It's made to
be easy to embed in other PySide/PyQt applications and comes with some examples that
show how this can be done. The interpreter can run in a separate thread, in
the UI main thread or in a gevent task. Qonsole is a fork of [pyqtconsole](https://github.com/pyqtconsole/pyqtconsole). The two diverged at pyqtconsole v1.3.0, and it is not quite a drop-in replacement, but does implement new features and has various improvements.

## Simple usage

The following snippet shows how to create a console that will execute user
input in a separate thread. Be aware that long running tasks will still block
the main thread due to the GIL. See the ``examples`` directory for more
examples.

```python
import sys
from threading import Thread
from PyQt5.QtWidgets import QApplication

from qonsole import PythonConsole

app = QApplication([])
console = PythonConsole()
console.show()
console.eval_in_thread()

sys.exit(app.exec_())
```

## Embedding

* *Separate thread* - Runs the interpreter in a separate thread, see the
  example `threaded.py`. Running the interpreter in a separate thread obviously
  limits the interaction with the Qt application. The parts of Qt that needs
  to be called from the main thread will not work properly, but is excellent
  way for having a 'plain' python console in your Qt app.

* *main thread* - Runs the interpreter in the main thread, see the example
  `inuithread.py`. Makes full interaction with Qt possible, lenghty operations
  will of course freeze the UI (as any lenghty operation that is called from
  the main thread). This is a great alternative for people who does not want
  to use the gevent based approach but still wants full interactivity with Qt.

* *gevent* - Runs the interpreter in a gevent task, see the example
  `_gevent.py`. Allows for full interactivity with Qt without special
  consideration (at least to some extent) for longer running processes. The
  best method if you want to use pyQtgraph, Matplotlib, PyMca or similar.

## Features

### Syntax highlighting

Syntax highlighting is provided by the [https://pygments.org](pygments) library.
Simply pass the Pygments style string to the ``PythonConsole`` constructer like so:

```python
console = PythonConsole(pygments_style='github-dark')
```

### Magic commands

Commands that start with `%` are magic commands.
This features provides IPython-like [magic commands](https://ipython.readthedocs.io/en/stable/interactive/magics.html) such as:

 * `%pwd` -- Print current working directory
 * `%cd` -- Change directory
 * `%ls` -- List directory contents
 * `%who` -- List variable names in the current namespace
 * `%whos` -- Display detailed variable information
 * `%timeit` -- Time the execution of a Python statement
 * `%run` -- Execute a Python script file
 * `%clear` -- Clear the console display
 * `%help` -- Display help message for magic commands

 In addition, custom magic commands can be defined by using the `add_magic_command()` method. Example:

```python
def version(args=None):
    return '2.0.0'

console = PythonConsole()
console.add_magic_command("version", version)
```

Which can be used like so:

```
   IN [0]: %version
           2.0.0
```

### Clear console

A local method, named `clear()`, is available to clear the input screen and reset the line numbering.
Enable it by pushing the method into the available namespace in the console:

```python
   console.interpreter.locals["clear"] = console.clear
```

### Shell commands

Commands entered in the console that start with `!` will be executed as shell commands.
The output of the command will be printed in the console.
For example, on a Linux or macOS system, entering `!ls -l` will list the files in the current directory. Example:

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

This module depends on [QtPy](https://github.com/spyder-ide/qtpy) which provides a compatibility layer for
Qt. The console is tested under both Qt5 and Qt6.

## Development

To generate coverage information for the unit tests, run `coverage run -m pytest tests/ && coverage report -m && coverage html`