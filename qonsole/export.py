"""Export functionality for qonsole console sessions.

Provides functions to export console sessions as Python scripts (.py) or
Jupyter notebooks (.ipynb) with captured outputs.
"""

import json
import os
from typing import Optional

from qtpy.QtWidgets import QFileDialog, QWidget


def export_session(
    commands: list[str],
    command_outputs: list[tuple[str, str, bool]],
    parent: Optional[QWidget] = None,
    filepath: Optional[str] = None,
    strip_prompts: bool = True,
) -> bool:
    """Export console session as a Python script or Jupyter notebook.

    Opens a file dialog to select save location if filepath is not provided.
    If the file extension is .ipynb, exports as a Jupyter notebook with
    code cells and captured outputs. Otherwise, exports as a Python script.
    Magic commands (%) and shell commands (!) are exported as comments in
    .py files, or as code cells with magic syntax in .ipynb files.

    Args:
        commands: List of command strings from command history.
        command_outputs: List of (command, output, is_error) tuples for
            associating outputs with commands in notebook export.
        parent: Parent widget for the file dialog. Defaults to None.
        filepath: Optional path to save the script. If None, opens a file dialog.
        strip_prompts: If True, removes empty lines and cleans up the output.
            Defaults to True.

    Returns:
        True if export was successful, False if cancelled or failed.
    """
    if not commands:
        return False

    # Open file dialog if no filepath provided
    if not filepath:
        filepath, _ = QFileDialog.getSaveFileName(
            parent,
            "Export Console Session",
            "console_session.py",
            "Python Files (*.py);;Jupyter Notebook (*.ipynb);;All Files (*)",
        )

        # User cancelled the dialog
        if not filepath:
            return False

    # Check file extension to determine export format
    _, ext = os.path.splitext(filepath)
    is_notebook = ext.lower() == ".ipynb"

    try:
        if is_notebook:
            # Export as Jupyter notebook
            return export_as_notebook(
                filepath, commands, command_outputs, strip_prompts
            )
        else:
            # Export as Python script
            return export_as_python_script(filepath, commands, strip_prompts)

    except Exception as e:
        print(f"Error exporting: {e}")
        return False


def export_as_python_script(
    filepath: str, commands: list[str], strip_prompts: bool = True
) -> bool:
    """Export commands as a Python script file.

    Magic commands (%) and shell commands (!) are exported as comments
    since they are not valid Python code.

    Args:
        filepath: Path to save the script.
        commands: List of commands to export.
        strip_prompts: Whether to clean up the output by skipping empty
            commands. Defaults to True.

    Returns:
        True if successful, False otherwise.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        # Write header comment
        f.write("#!/usr/bin/env python\n")

        # Write each command
        for cmd in commands:
            if strip_prompts:
                # Skip empty commands
                if not cmd.strip():
                    continue

                # Check if this is a magic or shell command
                stripped = cmd.lstrip()
                is_special = stripped.startswith("%") or stripped.startswith("!")

                if is_special:
                    # Comment out magic and shell commands
                    # Handle multi-line commands by commenting each line
                    lines = cmd.split("\n")
                    for line in lines:
                        if line.strip():  # Only write non-empty lines
                            f.write(f"# {line}\n")
                    # Add blank line after special commands
                    f.write("\n")
                else:
                    # Write regular Python commands as-is
                    f.write(cmd)
                    # Ensure proper newline separation
                    if not cmd.endswith("\n"):
                        f.write("\n")
                    # Add blank line between multi-line blocks for readability
                    if "\n" in cmd:
                        f.write("\n")
            else:
                # Write command as-is
                f.write(cmd)
                if not cmd.endswith("\n"):
                    f.write("\n")

    return True


def export_as_notebook(
    filepath: str,
    commands: list[str],
    command_outputs: list[tuple[str, str, bool]],
    strip_prompts: bool = True,
) -> bool:
    """Export commands as a Jupyter notebook (.ipynb) file.

    Creates a Jupyter notebook with code cells for each command and includes
    captured outputs (stdout, stderr, and return values) for each cell.

    Args:
        filepath: Path to save the notebook.
        commands: List of commands to export.
        command_outputs: List of (command, output, is_error) tuples for
            associating outputs with commands.
        strip_prompts: Whether to skip empty commands. Defaults to True.

    Returns:
        True if successful, False otherwise.
    """
    # Create Jupyter notebook structure
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.9.0",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    # Add a markdown cell with metadata
    notebook["cells"].append(
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["# Console Session"],
        }
    )

    # Create a mapping of commands to outputs
    output_map = {cmd: (output, is_error) for cmd, output, is_error in command_outputs}

    # Convert commands to notebook cells
    # Group contiguous comment lines into markdown cells
    markdown_buffer = []

    def flush_markdown():
        """Flush accumulated markdown lines as a markdown cell."""
        if markdown_buffer:
            notebook["cells"].append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": markdown_buffer.copy(),
                }
            )
            markdown_buffer.clear()

    for cmd in commands:
        if strip_prompts and not cmd.strip():
            continue

        # Check if this is a comment line (starts with #)
        stripped_cmd = cmd.lstrip()
        is_comment = stripped_cmd.startswith("#")

        if is_comment:
            # Add to markdown buffer
            # Remove the leading # and optional space
            lines = cmd.split("\n")
            for line in lines:
                stripped_line = line.lstrip()
                if stripped_line.startswith("#"):
                    # Remove # and optional following space
                    content = stripped_line[1:]
                    if content.startswith(" "):
                        content = content[1:]
                    markdown_buffer.append(content + "\n")
                elif stripped_line:  # Non-comment line in multi-line comment
                    markdown_buffer.append(line + "\n")
            continue

        # Not a comment - flush any accumulated markdown first
        flush_markdown()

        # Create a code cell for this command
        # Remove trailing newline for proper notebook formatting
        source_lines = cmd.rstrip("\n").split("\n")
        # Add newline to each line except the last one
        source = [line + "\n" for line in source_lines[:-1]]
        if source_lines:
            source.append(source_lines[-1])

        # Get the output for this command if available
        outputs = []
        if cmd in output_map:
            output_text, is_error = output_map[cmd]
            if output_text:
                # Create output structure
                if is_error:
                    # Format as error output
                    outputs.append(
                        {
                            "output_type": "error",
                            "ename": "Error",
                            "evalue": "",
                            "traceback": output_text.split("\n"),
                        }
                    )
                else:
                    # Format as stream output (stdout)
                    outputs.append(
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": output_text,
                        }
                    )

        notebook["cells"].append(
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": outputs,
                "source": source,
            }
        )

    # Flush any remaining markdown at the end
    flush_markdown()

    # Write the notebook file
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    return True
