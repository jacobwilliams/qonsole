"""Test stream redirection functionality."""

import pytest
from qtpy.QtCore import QObject, Signal

from qonsole.stream import Stream


class MockReceiver(QObject):
    """Mock object to receive stream signals."""

    signal_received = Signal(str)

    def __init__(self):
        super().__init__()
        self.messages = []
        self.signal_received.connect(self._on_message)

    def _on_message(self, msg):
        self.messages.append(msg)


class TestStream:
    """Test Stream."""

    @pytest.fixture
    def receiver(self, qtbot):
        """Create a mock receiver."""
        return MockReceiver()

    @pytest.fixture
    def stream(self, receiver):
        """Create a Stream."""
        stream = Stream()
        stream.write_event.connect(receiver._on_message)
        return stream

    def test_write(self, stream, receiver, qtbot):
        """Test writing to stream."""
        stream.write("hello")
        stream.flush()

        # Wait for signal
        qtbot.wait(100)

        assert len(receiver.messages) > 0
        assert "hello" in "".join(receiver.messages)

    def test_write_multiple(self, stream, receiver, qtbot):
        """Test multiple writes."""
        stream.write("line1\n")
        stream.write("line2\n")
        stream.flush()

        qtbot.wait(100)

        combined = "".join(receiver.messages)
        assert "line1" in combined
        assert "line2" in combined

    def test_flush(self, stream):
        """Test flush method exists and doesn't crash."""
        stream.flush()  # Should not raise

    def test_writable(self, stream):
        """Test stream is writable."""
        # Stream should support write operations
        stream.write("test")
        assert True  # If we got here, it's writable

    def test_readline_not_supported(self, stream):
        """Test that readline raises NotImplementedError."""
        # readline should not be supported - qonsole doesn't support input()
        with pytest.raises(NotImplementedError) as exc_info:
            stream.readline()

        # Verify the error message is helpful
        error_msg = str(exc_info.value)
        assert "not supported" in error_msg.lower()
        assert "input()" in error_msg or "stdin" in error_msg.lower()
