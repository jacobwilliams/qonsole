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
        """Read a line from the stream, blocking until a newline is available.

        Waits for data with a newline character to be available in the buffer.
        If a timeout is specified and expires, returns whatever data is available.

        Args:
            timeout: Optional timeout in seconds. None means wait indefinitely.

        Returns:
            A string containing a line of text including the newline character,
            or an empty string if timeout expires with no data.
        """
        data = ""

        try:
            with self._line_cond:
                first_linesep = self._buffer.find("\n")

                # Is there already some lines in the buffer, write might have
                # been called before we read !
                while first_linesep == -1:
                    notfied = self._line_cond.wait(timeout)
                    first_linesep = self._buffer.find("\n")

                    # We had a timeout, break !
                    if not notfied:
                        break

                # Check if there really is something in the buffer after
                # waiting for line_cond. There might have been a timeout, and
                # there is still no data available
                if first_linesep > -1:
                    data = self._buffer[0 : first_linesep + 1]

                    if len(self._buffer) > len(data):
                        self._buffer = self._buffer[first_linesep + 1 :]
                    else:
                        self._buffer = ""

        # Tricky RuntimeError !, wait releases the lock and waits for notify
        # and then acquire the lock again !. There might be an exception, i.e
        # KeyboardInterupt which interrupts the wait. The cleanup of the with
        # statement then tries to release the lock which is not acquired,
        # causing a RuntimeError. puh ! If its the case just try again !
        except RuntimeError:
            data = self.readline(timeout)

        return data

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
