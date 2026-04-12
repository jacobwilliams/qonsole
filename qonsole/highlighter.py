"""Syntax highlighting for the console.

Provides syntax highlighting for Python code and prompts using Pygments.
"""

from bisect import bisect_right
from collections.abc import Generator
from typing import Optional

from ipython_pygments_lexers import IPythonLexer as PythonLexer
from pygments import lex
from pygments.styles import get_style_by_name
from pygments.token import Token
from qtpy.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextBlockUserData,
    QTextCharFormat,
)


class NoHighlightData(QTextBlockUserData):
    """User data to mark blocks that should not be syntax highlighted."""

    pass


class ErrorHighlightData(QTextBlockUserData):
    """User data to mark blocks that contain errors."""

    pass


def _find_token_style(style: object, token_type: object) -> Optional[str]:
    """Walk up token hierarchy to find a style string.

    Args:
        style: Pygments style object
        token_type: Token type to find style for

    Returns:
        Style string if found, None otherwise
    """
    current = token_type
    while current:
        style_string = style.styles.get(current)
        if style_string:
            return style_string
        current = getattr(current, "parent", None)
    return None


def pygments_style_to_format(style_dict: Optional[str]) -> Optional[QTextCharFormat]:
    """Convert a Pygments style dictionary entry to QTextCharFormat.

    Pygments style format: "#rrggbb bg:#rrggbb bold italic underline"

    Args:
        style_dict: Pygments style string or None.

    Returns:
        QTextCharFormat with parsed styles, or None if style_dict is empty.
    """
    if not style_dict:
        return None

    _format = QTextCharFormat()

    # Parse the style string
    parts = str(style_dict).split()
    for part in parts:
        if part.startswith("#"):
            # Foreground color
            _format.setForeground(QColor(part))
        elif part.startswith("bg:#"):
            # Background color
            _format.setBackground(QColor(part[3:]))
        elif part == "bold":
            _format.setFontWeight(QFont.Bold)
        elif part == "italic":
            _format.setFontItalic(True)
        elif part == "underline":
            _format.setFontUnderline(True)

    return _format


def build_token_style_map(
    style_name: str, token_map: dict[str, object]
) -> dict[str, QTextCharFormat]:
    """Build a style map from Pygments theme for specific tokens.

    Args:
        style_name: Name of Pygments style (e.g., 'monokai')
        token_map: Dict mapping style keys to Token types

    Returns:
        Dict mapping style keys to QTextCharFormat objects
    """
    style = get_style_by_name(style_name)
    styles: dict[str, QTextCharFormat] = {}

    for key, token_type in token_map.items():
        styles[key] = pygments_style_to_format(_find_token_style(style, token_type))

    return styles


class PromptHighlighter:
    """Syntax highlighter for console input/output prompts.

    Applies formatting to prompt text (e.g., "IN [1]:" and "OUT[1]:")
    using Pygments color schemes.
    """

    def __init__(self, pygments_style: str) -> None:
        """Initialize the prompt highlighter.

        Args:
            pygments_style: Name of Pygments style to use (e.g., 'monokai').
        """
        self.updateStyle(pygments_style)

    def updateStyle(self, style_name: str) -> None:
        """Change the Pygments color scheme for prompts.

        Args:
            style_name: Name of Pygments style (e.g., 'monokai', 'vim')
        """
        try:
            token_map = {
                "inprompt": Token.Comment,
                "outprompt": Token.Comment,
            }
            self.styles = build_token_style_map(style_name, token_map)
        except Exception:
            print(f"Error: Pygments style '{style_name}' not found.")
            return

    def highlight(
        self, text: str, is_output: bool = False
    ) -> Generator[tuple[int, int, QTextCharFormat], None, None]:
        """Apply prompt formatting to entire text.

        Args:
            text: The prompt text to highlight.
            is_output: True for output prompts, False for input prompts.
                Defaults to False.

        Yields:
            Tuple of (start_index, length, format) for highlighted regions.
        """
        if not text:
            return

        # Use outprompt color for output prompts, inprompt for input prompts
        fmt = self.styles["outprompt"] if is_output else self.styles["inprompt"]

        # Return formatting for entire text
        yield (0, len(text), fmt)


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code using Pygments.

    Provides context-aware syntax highlighting for Python code with support
    for Pygments color schemes.
    """

    def __init__(self, document: object, pygments_style: str) -> None:
        """Initialize the Python syntax highlighter.

        Args:
            document: The QTextDocument to highlight.
            pygments_style: Name of Pygments style to use (e.g., 'monokai',
                'vim', 'friendly').
        """
        QSyntaxHighlighter.__init__(self, document)

        self.lexer = PythonLexer()
        self.token_formats = self._build_pygments_token_formats(pygments_style)

        # Cache tokenized document by content hash
        self._cached_doc_text: Optional[str] = None
        self._line_formats: dict[int, list[tuple[int, int, QTextCharFormat]]] = {}
        self._doc_revision: int = -1  # Track document revision for efficiency

    def _build_pygments_token_formats(
        self, style_name: str
    ) -> dict[object, QTextCharFormat]:
        """Build token format map from Pygments style.

        Args:
            style_name: Name of Pygments style (e.g., 'monokai').

        Returns:
            Dict mapping Token types to QTextCharFormat objects.
        """
        style = get_style_by_name(style_name)
        token_formats: dict[object, QTextCharFormat] = {}

        # Convert each token type in the style
        # style.styles is a dict: {token_type: style_string}
        for token_type, style_string in style.styles.items():
            token_formats[token_type] = pygments_style_to_format(style_string)

        return token_formats

    def updateStyle(self, style_name: str) -> None:
        """Change the Pygments color scheme and re-highlight the document.

        Args:
            style_name: Name of Pygments style (e.g., 'monokai', 'vim')
        """
        try:
            self.token_formats = self._build_pygments_token_formats(style_name)
        except Exception:
            print(f"Error: Pygments style '{style_name}' not found.")
            return
        self._cached_doc_text = None  # Clear cache to force retokenization
        self._doc_revision = -1  # Reset revision counter
        self._line_formats = {}
        self.rehighlight()  # Trigger re-highlighting of entire document

    def _to_utf16_offset(self, text: str, position: int) -> int:
        """Convert Python string position to UTF-16 offset for Qt.

        Qt uses UTF-16 encoding internally, where some characters
        (like emoji) take 2 code units. This converts Python string
        indices to UTF-16 positions.

        Args:
            text: The text string.
            position: Python string position (0-indexed).

        Returns:
            UTF-16 offset corresponding to the position.
        """
        return len(text[:position].encode("utf-16-le")) // 2

    def highlightBlock(self, text: str) -> None:
        """Apply syntax highlighting to a text block.

        Called by Qt for each visible text block. Uses cached tokenization
        results for efficient highlighting.

        Args:
            text: The text of the block to highlight.
        """
        # Skip highlighting if the block is marked with NoHighlightData
        if isinstance(self.currentBlock().userData(), NoHighlightData):
            return
        if isinstance(self.currentBlock().userData(), ErrorHighlightData):
            # If block contains an error, apply error formatting to entire block
            error_fmt = self._get_format_for_token(Token.Generic.Error)
            if error_fmt:
                self.setFormat(0, len(text), error_fmt)
            return

        if not text:
            return

        block_num = self.currentBlock().blockNumber()

        # Use document revision to efficiently detect changes
        # Get text first, then check revision to ensure they match
        doc_text = self.document().toPlainText()
        current_revision = self.document().revision()

        # Only retokenize if document revision changed
        if current_revision != self._doc_revision:
            self._line_formats = self._tokenize_document(doc_text)
            # Update cached values atomically after successful tokenization
            self._cached_doc_text = doc_text
            self._doc_revision = current_revision

        # Apply formatting for current line
        if block_num in self._line_formats:
            for start, length, fmt in self._line_formats[block_num]:
                self.setFormat(start, length, fmt)

    def _tokenize_document(
        self, text: str
    ) -> dict[int, list[tuple[int, int, QTextCharFormat]]]:
        """Tokenize entire document, return formatting by line number.

        This method is necessary because Pygments requires the entire document
        for context-aware syntax highlighting. Qt's QSyntaxHighlighter only
        provides one line at a time via highlightBlock(), but Pygments needs
        full context to properly handle:
        - Multi-line strings (triple-quoted strings)
        - Nested block structures (indentation-based syntax)
        - Context-dependent tokens (keywords vs identifiers)

        We tokenize the entire document once and cache the formatting positions
        by line number. Each line can then be highlighted independently using
        the cached token positions.

        Args:
            text: The complete document text

        Returns:
            dict: Maps line numbers to lists of (start, length, format) tuples
        """
        line_formats: dict[int, list[tuple[int, int, QTextCharFormat]]] = {}
        if not text:
            return line_formats

        # Build text from only the blocks that should be highlighted
        # Skip blocks with NoHighlightData or ErrorHighlightData
        doc = self.document()
        block = doc.begin()
        block_map = {}  # Maps text line to block number
        code_lines = []  # Only code that should be highlighted
        text_line = 0

        while block.isValid():
            user_data = block.userData()
            block_text = block.text()
            # Skip blocks marked as no-highlight, error, or empty blocks
            if (
                not isinstance(user_data, (NoHighlightData, ErrorHighlightData))
                and block_text.strip()
            ):
                block_map[text_line] = block.blockNumber()
                code_lines.append(block_text)
                text_line += 1
            block = block.next()

        # Join the code lines for tokenization
        code_text = "\n".join(code_lines)
        if not code_text:
            return line_formats

        lines = code_lines
        line_starts = [0]
        for line in lines[:-1]:
            line_starts.append(line_starts[-1] + len(line) + 1)

        position = 0
        for token_type, token_value in lex(code_text, self.lexer):
            if not token_value:
                continue

            fmt = self._get_format_for_token(token_type)
            if not fmt:
                position += len(token_value)
                continue

            # Find which line this token starts on using binary search
            start_line = bisect_right(line_starts, position) - 1

            # Handle tokens across multiple lines
            current_line = start_line
            chars_processed = 0

            while chars_processed < len(token_value) and current_line < len(lines):
                line_start_pos = line_starts[current_line]
                line_text = lines[current_line]

                # Position within current line
                token_pos_in_line = max(0, position + chars_processed - line_start_pos)

                # How many chars of token on this line
                remaining = len(token_value) - chars_processed
                chars_on_line = min(remaining, len(line_text) - token_pos_in_line)

                if chars_on_line > 0:
                    utf16_start = self._to_utf16_offset(line_text, token_pos_in_line)
                    utf16_end = self._to_utf16_offset(
                        line_text, token_pos_in_line + chars_on_line
                    )

                    # Map back to actual block number
                    block_num = block_map.get(current_line)
                    if block_num is not None:
                        if block_num not in line_formats:
                            line_formats[block_num] = []
                        line_formats[block_num].append(
                            (utf16_start, utf16_end - utf16_start, fmt)
                        )

                    chars_processed += chars_on_line

                # Skip the newline character
                if chars_processed < len(token_value):
                    chars_processed += 1
                    current_line += 1

            position += len(token_value)

        return line_formats

    def _get_format_for_token(self, token_type: object) -> Optional[QTextCharFormat]:
        """Find the most specific format for a token type.

        Walks up the token hierarchy until a format is found.

        Args:
            token_type: Pygments Token type to find format for.

        Returns:
            QTextCharFormat if found, None otherwise.
        """
        current_type = token_type
        while current_type:
            fmt = self.token_formats.get(current_type)
            if fmt:
                return fmt
            current_type = getattr(current_type, "parent", None)
        return None
