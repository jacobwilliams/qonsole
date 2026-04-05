"""Prompt area widget for the console.

Provides the PromptArea widget that displays input/output prompts
on the left side of the console text area.
"""

from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import QRect, Qt
from qtpy.QtGui import QPainter
from qtpy.QtWidgets import QWidget

if TYPE_CHECKING:
    from qtpy.QtGui import QTextBlock


class PromptArea(QWidget):
    """Widget that displays the prompts on the left of the input area.

    Shows input prompts (e.g., "IN [1]:") and output prompts (e.g., "OUT[1]:")
    synchronized with the text in the main editor area.
    """

    def __init__(
        self,
        edit: QWidget,
        get_text: Callable[[int], tuple[str, bool]],
        highlighter: object,
    ) -> None:
        """Initialize the prompt area widget.

        Args:
            edit: The text editor widget to display prompts for.
            get_text: Callable that returns (prompt_text, is_output) for a line number.
            highlighter: Highlighter instance for syntax highlighting prompts.
        """
        super().__init__(edit)
        self.setFixedWidth(0)
        self.edit = edit
        self.get_text = get_text
        self.highlighter = highlighter
        edit.updateRequest.connect(self.updateContents)

    def paintEvent(self, event):
        """Paint the prompt area.

        Renders all visible prompt lines with appropriate formatting.

        Args:
            event: QPaintEvent containing the region to repaint.
        """
        edit = self.edit
        height = edit.fontMetrics().height()
        block = edit.firstVisibleBlock()
        count = block.blockNumber()
        painter = QPainter(self)
        painter.fillRect(event.rect(), edit.palette().base())
        first = True
        while block.isValid():
            count += 1
            block_top = (
                edit.blockBoundingGeometry(block).translated(edit.contentOffset()).top()
            )
            if not block.isVisible() or block_top > event.rect().bottom():
                break
            rect = QRect(0, int(block_top), self.width(), height)
            self.draw_block(painter, rect, block, first)
            first = False
            block = block.next()
        painter.end()
        super().paintEvent(event)

    def updateContents(self, rect: QRect, scroll: int) -> None:
        """Update the prompt area when the editor changes.

        Args:
            rect: Rectangle that needs updating.
            scroll: Vertical scroll amount in pixels.
        """
        if scroll:
            self.scroll(0, scroll)
        else:
            self.update()

    def adjust_width(self, new_text: str) -> None:
        """Adjust the width of the prompt area to fit new text.

        Args:
            new_text: Text string to calculate required width for.
        """
        width = calc_text_width(self.edit, new_text)
        if width > self.width():
            self.setFixedWidth(width)

    def draw_block(
        self, painter: QPainter, rect: QRect, block: "QTextBlock", first: bool
    ) -> None:
        """Draw the prompt for a given text block.

        Renders the prompt text corresponding to a line of the text document,
        with appropriate syntax highlighting.

        Args:
            painter: QPainter to use for drawing.
            rect: Rectangle defining the draw area.
            block: QTextBlock to draw the prompt for.
            first: Whether this is the first visible block.
        """
        pen = painter.pen()
        text, is_output = self.get_text(block.blockNumber())

        default = self.edit.currentCharFormat()
        formats = [default] * len(text)
        painter.setFont(self.edit.font())

        for index, length, format in self.highlighter.highlight(
            text, is_output=is_output
        ):
            formats[index : index + length] = [format] * length

        for idx, (_char, format) in enumerate(zip(text, formats)):
            rpos = len(text) - idx - 1
            pen.setColor(format.foreground().color())
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignRight, text[idx] + " " * rpos)


def calc_text_width(widget: QWidget, text: str) -> int:
    """Estimate the width that the given text would take within the widget.

    Args:
        widget: QWidget to calculate text width for.
        text: Text string to measure.

    Returns:
        Estimated width in pixels required to display the text.
    """
    return (
        widget.fontMetrics().width(text)
        + widget.fontMetrics().width("M")
        + widget.contentsMargins().left()
        + widget.contentsMargins().right()
    )
