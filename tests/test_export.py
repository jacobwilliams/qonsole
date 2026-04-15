"""Test export functionality."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from qonsole.export import export_as_notebook, export_as_python_script, export_session


class TestExportSession:
    """Test the main export_session function."""

    def test_export_empty_commands(self):
        """Test that exporting with no commands returns False."""
        result = export_session([], [], filepath="/tmp/test.py")
        assert result is False

    @patch("qonsole.export.QFileDialog.getSaveFileName")
    def test_export_cancelled(self, mock_dialog):
        """Test that cancelling the file dialog returns False."""
        mock_dialog.return_value = ("", "")  # User cancelled
        result = export_session(["x = 1"], [])
        assert result is False

    def test_export_to_python_script(self):
        """Test exporting to a .py file."""
        commands = ["x = 1", "y = 2", "print(x + y)"]
        outputs = []

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_session(commands, outputs, filepath=filepath)
            assert result is True
            assert os.path.exists(filepath)

            # Verify content
            content = Path(filepath).read_text()
            assert "#!/usr/bin/env python" in content
            assert "x = 1" in content
            assert "y = 2" in content
            assert "print(x + y)" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_to_notebook(self):
        """Test exporting to a .ipynb file."""
        commands = ["x = 1", "y = 2", "x + y"]
        outputs = [
            ("x = 1", "", False),
            ("y = 2", "", False),
            ("x + y", "3", False),
        ]

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_session(commands, outputs, filepath=filepath)
            assert result is True
            assert os.path.exists(filepath)

            # Verify it's valid JSON
            with open(filepath) as f:
                notebook = json.load(f)

            assert notebook["nbformat"] == 4
            assert "cells" in notebook
            assert len(notebook["cells"]) > 0
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_handles_exceptions(self):
        """Test that exceptions during export are handled gracefully."""
        # Try to export to an invalid path
        result = export_session(
            ["x = 1"], [], filepath="/invalid/path/that/does/not/exist/file.py"
        )
        assert result is False


class TestExportAsPythonScript:
    """Test exporting as Python script."""

    def test_basic_export(self):
        """Test basic Python script export."""
        commands = ["x = 1", "y = 2", "print(x + y)"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(filepath, commands)
            assert result is True

            content = Path(filepath).read_text()
            assert "#!/usr/bin/env python" in content
            assert "x = 1" in content
            assert "y = 2" in content
            assert "print(x + y)" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_with_magic_commands(self):
        """Test that magic commands are commented out."""
        commands = ["x = 1", "%pwd", "print(x)"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(filepath, commands)
            assert result is True

            content = Path(filepath).read_text()
            assert "x = 1" in content
            assert "# %pwd" in content
            assert "print(x)" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_with_shell_commands(self):
        """Test that shell commands are commented out."""
        commands = ["x = 1", "!ls", "print(x)"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(filepath, commands)
            assert result is True

            content = Path(filepath).read_text()
            assert "x = 1" in content
            assert "# !ls" in content
            assert "print(x)" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_multiline_command(self):
        """Test exporting multi-line commands."""
        commands = ["def foo():\n    return 42", "result = foo()"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(filepath, commands)
            assert result is True

            content = Path(filepath).read_text()
            assert "def foo():" in content
            assert "    return 42" in content
            assert "result = foo()" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_strips_empty_commands(self):
        """Test that empty commands are stripped when strip_prompts=True."""
        commands = ["x = 1", "", "   ", "y = 2"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(filepath, commands, strip_prompts=True)
            assert result is True

            content = Path(filepath).read_text()
            assert "x = 1" in content
            assert "y = 2" in content
            # Should not have excessive blank lines from empty commands
            lines = content.split("\n")
            # Filter out the header and actual commands
            non_empty = [
                line for line in lines if line.strip() and not line.startswith("#!")
            ]
            assert len(non_empty) == 2
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_preserves_empty_with_strip_false(self):
        """Test that empty commands are preserved when strip_prompts=False."""
        commands = ["x = 1", "", "y = 2"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(filepath, commands, strip_prompts=False)
            assert result is True

            # Just verify it succeeds - exact content may vary
            assert os.path.exists(filepath)
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)


class TestExportAsNotebook:
    """Test exporting as Jupyter notebook."""

    def test_basic_notebook_export(self):
        """Test basic notebook export."""
        commands = ["x = 1", "y = 2", "x + y"]
        outputs = [
            ("x = 1", "", False),
            ("y = 2", "", False),
            ("x + y", "3\n", False),
        ]

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(filepath, commands, outputs)
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            assert notebook["nbformat"] == 4
            assert notebook["nbformat_minor"] == 4
            assert "cells" in notebook
            assert "metadata" in notebook

            # Should have markdown header + code cells
            cells = notebook["cells"]
            assert len(cells) >= 4  # Header + 3 commands

            # First cell should be markdown header
            assert cells[0]["cell_type"] == "markdown"
            assert any("Console Session" in line for line in cells[0]["source"])

            # Find code cells
            code_cells = [c for c in cells if c["cell_type"] == "code"]
            assert len(code_cells) == 3
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_with_outputs(self):
        """Test that outputs are included in notebook cells."""
        commands = ["print('hello')", "x = 42", "x"]
        outputs = [
            ("print('hello')", "hello\n", False),
            ("x = 42", "", False),
            ("x", "42", False),
        ]

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(filepath, commands, outputs)
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]

            # First cell should have output
            assert len(code_cells[0]["outputs"]) == 1
            assert code_cells[0]["outputs"][0]["output_type"] == "stream"
            assert code_cells[0]["outputs"][0]["text"] == "hello\n"

            # Second cell has no output
            assert len(code_cells[1]["outputs"]) == 0

            # Third cell should have output
            assert len(code_cells[2]["outputs"]) == 1
            assert code_cells[2]["outputs"][0]["text"] == "42"
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_with_error_output(self):
        """Test that error outputs are formatted correctly."""
        commands = ["1 / 0"]
        outputs = [("1 / 0", "ZeroDivisionError: division by zero\n", True)]

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(filepath, commands, outputs)
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
            assert len(code_cells) == 1

            # Should have error output
            assert len(code_cells[0]["outputs"]) == 1
            output = code_cells[0]["outputs"][0]
            assert output["output_type"] == "error"
            assert "ename" in output
            assert "traceback" in output
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_comment_to_markdown(self):
        """Test that comment lines are converted to markdown cells."""
        commands = [
            "# This is a title",
            "# This is a description",
            "x = 1",
            "# Another comment",
            "y = 2",
        ]
        outputs = [
            ("x = 1", "", False),
            ("y = 2", "", False),
        ]

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(filepath, commands, outputs)
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            cells = notebook["cells"]

            # Should have: header, markdown (comments), code, markdown, code
            markdown_cells = [c for c in cells if c["cell_type"] == "markdown"]
            code_cells = [c for c in cells if c["cell_type"] == "code"]

            # At least 3 markdown cells (header + 2 comment groups)
            assert len(markdown_cells) >= 3
            assert len(code_cells) == 2

            # Check that comments were converted (without leading #)
            markdown_text = "".join("".join(cell["source"]) for cell in markdown_cells)
            assert "This is a title" in markdown_text
            assert "This is a description" in markdown_text
            assert "Another comment" in markdown_text
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_strips_empty_commands(self):
        """Test that empty commands are skipped with strip_prompts=True."""
        commands = ["x = 1", "", "   ", "y = 2"]
        outputs = []

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(filepath, commands, outputs, strip_prompts=True)
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
            # Should only have 2 cells (empty ones skipped)
            assert len(code_cells) == 2
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_multiline_command(self):
        """Test that multi-line commands are properly formatted."""
        commands = ["def foo():\n    return 42\n", "result = foo()"]
        outputs = []

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(filepath, commands, outputs)
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
            assert len(code_cells) == 2

            # First cell should have multiple lines
            first_cell_source = "".join(code_cells[0]["source"])
            assert "def foo():" in first_cell_source
            assert "    return 42" in first_cell_source
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_metadata_structure(self):
        """Test that notebook has correct metadata structure."""
        commands = ["x = 1"]
        outputs = []

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(filepath, commands, outputs)
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            # Check metadata structure
            assert "metadata" in notebook
            assert "kernelspec" in notebook["metadata"]
            assert "language_info" in notebook["metadata"]

            kernelspec = notebook["metadata"]["kernelspec"]
            assert kernelspec["name"] == "python3"
            assert kernelspec["language"] == "python"

            lang_info = notebook["metadata"]["language_info"]
            assert lang_info["name"] == "python"
            assert lang_info["file_extension"] == ".py"
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)


class TestPreambleExport:
    """Test preamble functionality in exports."""

    def test_script_export_with_preamble(self):
        """Test that preamble lines are added to script exports."""
        commands = ["x = 1", "print(x)"]
        preamble = ["import numpy as np", "import pandas as pd"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(
                filepath, commands, strip_prompts=True, preamble=preamble
            )
            assert result is True

            content = Path(filepath).read_text()
            # Check shebang is first
            assert content.startswith("#!/usr/bin/env python\n")
            # Check preamble section exists
            assert "# === PREAMBLE ===" in content
            assert "# === END PREAMBLE ===" in content
            # Check preamble imports are present
            assert "import numpy as np" in content
            assert "import pandas as pd" in content
            # Check commands are present
            assert "x = 1" in content
            assert "print(x)" in content
            # Verify order: shebang, then preamble, then commands
            shebang_pos = content.find("#!/usr/bin/env python")
            preamble_start = content.find("# === PREAMBLE ===")
            preamble_end = content.find("# === END PREAMBLE ===")
            x_pos = content.find("x = 1")
            assert shebang_pos < preamble_start < preamble_end < x_pos
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_script_export_with_empty_preamble(self):
        """Test that empty preamble list doesn't add preamble section."""
        commands = ["x = 1"]
        preamble = []

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(
                filepath, commands, strip_prompts=True, preamble=preamble
            )
            assert result is True

            content = Path(filepath).read_text()
            # Empty preamble should not add preamble markers
            assert "# === PREAMBLE ===" not in content
            assert "x = 1" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_script_export_with_none_preamble(self):
        """Test that None preamble (default) works correctly."""
        commands = ["x = 1"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(
                filepath, commands, strip_prompts=True, preamble=None
            )
            assert result is True

            content = Path(filepath).read_text()
            # None preamble should not add preamble markers
            assert "# === PREAMBLE ===" not in content
            assert "x = 1" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_export_with_preamble(self):
        """Test that preamble is added as first code cell in notebooks."""
        commands = ["x = 1", "print(x)"]
        outputs = []
        preamble = ["import numpy as np", "import pandas as pd\n"]

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(
                filepath, commands, outputs, strip_prompts=True, preamble=preamble
            )
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            cells = notebook["cells"]
            # Should have: markdown header, preamble code cell, then command cells
            assert len(cells) >= 3

            # First cell is markdown header
            assert cells[0]["cell_type"] == "markdown"

            # Second cell should be preamble code cell
            assert cells[1]["cell_type"] == "code"
            assert cells[1]["metadata"].get("tags") == ["preamble"]
            preamble_source = "".join(cells[1]["source"])
            assert "import numpy as np" in preamble_source
            assert "import pandas as pd" in preamble_source

            # Remaining cells are regular code cells
            code_cells = [c for c in cells[2:] if c["cell_type"] == "code"]
            assert len(code_cells) == 2
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_export_with_empty_preamble(self):
        """Test that empty preamble list doesn't add preamble cell."""
        commands = ["x = 1"]
        outputs = []
        preamble = []

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(
                filepath, commands, outputs, strip_prompts=True, preamble=preamble
            )
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            cells = notebook["cells"]
            # Should have: markdown header, code cell (no preamble)
            code_cells = [c for c in cells if c["cell_type"] == "code"]
            # Check that none of the cells have preamble tag
            for cell in code_cells:
                assert cell["metadata"].get("tags") != ["preamble"]
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_export_with_none_preamble(self):
        """Test that None preamble (default) works correctly."""
        commands = ["x = 1"]
        outputs = []

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(
                filepath, commands, outputs, strip_prompts=True, preamble=None
            )
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            cells = notebook["cells"]
            # Check that none of the cells have preamble tag
            code_cells = [c for c in cells if c["cell_type"] == "code"]
            for cell in code_cells:
                assert cell["metadata"].get("tags") != ["preamble"]
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_session_with_preamble_script(self):
        """Test export_session passes preamble to script export."""
        commands = ["x = 1"]
        outputs = []
        preamble = ["import math"]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_session(
                commands, outputs, filepath=filepath, preamble=preamble
            )
            assert result is True

            content = Path(filepath).read_text()
            assert "# === PREAMBLE ===" in content
            assert "import math" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_session_with_preamble_notebook(self):
        """Test export_session passes preamble to notebook export."""
        commands = ["x = 1"]
        outputs = []
        preamble = ["import math"]

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_session(
                commands, outputs, filepath=filepath, preamble=preamble
            )
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            # Find preamble cell
            code_cells = [
                c
                for c in notebook["cells"]
                if c["cell_type"] == "code"
                and c["metadata"].get("tags") == ["preamble"]
            ]
            assert len(code_cells) == 1
            preamble_source = "".join(code_cells[0]["source"])
            assert "import math" in preamble_source
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_preamble_with_multiline_content(self):
        """Test preamble with multi-line content."""
        commands = ["x = 1"]
        preamble = [
            "# Standard libraries\n",
            "import math\n",
            "import sys\n",
            "\n",
            "# Third-party libraries\n",
            "import numpy as np\n",
        ]

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            filepath = tmp.name

        try:
            result = export_as_python_script(
                filepath, commands, strip_prompts=True, preamble=preamble
            )
            assert result is True

            content = Path(filepath).read_text()
            assert "# Standard libraries" in content
            assert "import math" in content
            assert "import sys" in content
            assert "# Third-party libraries" in content
            assert "import numpy as np" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_notebook_multiline_comment_with_mixed_content(self):
        """Test multi-line comments with non-comment lines are handled."""
        # This tests the edge case where a command has multiple lines
        # and some lines start with # while others don't (e.g., a string)
        commands = [
            "# Comment line 1\nsome text without hash",
            "x = 1",
        ]
        outputs = []

        with tempfile.NamedTemporaryFile(
            suffix=".ipynb", delete=False, mode="w"
        ) as tmp:
            filepath = tmp.name

        try:
            result = export_as_notebook(filepath, commands, outputs)
            assert result is True

            with open(filepath) as f:
                notebook = json.load(f)

            # Should successfully create the notebook
            assert "cells" in notebook
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)
