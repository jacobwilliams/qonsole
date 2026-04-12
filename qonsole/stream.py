"""Thread-safe stream for console I/O.

Provides a Stream class that enables thread-safe reading and writing,
used for redirecting stdin/stdout in the console.
"""

from threading import Condition
from typing import Optional

from qtpy.QtCore import QObject, Signal


class Stream(QObject):
    """Thread-safe I/O stream with Qt signal support.

    Provides a buffered stream for reading and writing data with thread
    synchronization. Emits Qt signals when data is written, flushed, or closed.

    Attributes:
        write_event: Signal emitted when data is written to the stream.
        flush_event: Signal emitted when the stream is flushed.
        close_event: Signal emitted when the stream is closed.
    """

    write_event = Signal(str)
    flush_event = Signal(str)
    close_event = Signal()

    def __init__(self) -> None:
        """Initialize the stream with an empty buffer."""
        super().__init__()
        self._line_cond: Condition = Condition()
        self._buffer: str = ""

    def _reset_buffer(self) -> str:
        """Clear the internal buffer and return its contents.

        Returns:
            The current buffer contents before clearing.
        """
        data = self._buffer
        self._buffer = ""
        return data

    def _flush(self) -> str:
        """Flush the buffer and notify waiting threads.

        Returns:
            The flushed buffer contents.
        """
        with self._line_cond:
            data = self._reset_buffer()
            self._line_cond.notify()

        return data

    def readline(self, timeout: Optional[float] = None) -> str:
        """Read a line from the stream - not supported in qonsole.

        The qonsole console does not support interactive input functions
        like input() or sys.stdin.readline(). Use print() for output instead.

        Args:
            timeout: Optional timeout in seconds (ignored).

        Raises:
            NotImplementedError: Always raised with a helpful error message.
        """
        raise NotImplementedError(
            "Interactive input (input() or sys.stdin.readline()) is not supported.\n"
            "The console is designed for output display and code execution, not for "
            "prompting user input during code execution."
        )

    def write(self, data: str) -> None:
        """Write data to the stream and emit write_event signal.

        Appends data to the internal buffer and notifies threads waiting
        to read if a newline character is present.

        Args:
            data: String data to write to the stream.
        """
        with self._line_cond:
            self._buffer += data

            if "\n" in self._buffer:
                self._line_cond.notify()

            self.write_event.emit(data)

    def flush(self) -> str:
        """Flush the stream buffer and emit flush_event signal.

        Returns:
            The flushed buffer contents.
        """
        data = self._flush()
        self.flush_event.emit(data)
        return data

    def close(self) -> None:
        """Close the stream and emit close_event signal."""
        self.close_event.emit()
