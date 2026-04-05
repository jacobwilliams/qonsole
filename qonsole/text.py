"""Text formatting utilities for the console.

Provides functions for finding common substrings and formatting text output
in columns for display in the console.
"""

from typing import Any, Optional, Union


def long_substr(data: list[str]) -> str:
    """Find the longest common substring across all strings in data.

    Args:
        data: List of strings to find common substring in.

    Returns:
        The longest substring common to all strings in data.
        Returns empty string if no common substring found.
        If data contains only one string, returns that string.
    """
    if not data:
        return ""
    if len(data) == 1:
        return data[0]

    # Use the shortest string as reference for efficiency
    shortest = min(data, key=len)
    if not shortest:
        return ""

    # Start with longest possible substrings and work down
    for length in range(len(shortest), 0, -1):
        for start in range(len(shortest) - length + 1):
            candidate = shortest[start : start + length]
            if all(candidate in s for s in data):
                return candidate

    return ""


default_opts: dict[str, Any] = {
    "arrange_array": False,  # Check if file has changed since last time
    "arrange_vertical": True,
    "array_prefix": "",
    "array_suffix": "",
    "colfmt": None,
    "colsep": "  ",
    "displaywidth": 80,
    "lineprefix": "",
    "linesuffix": "\n",
    "ljust": None,
    "term_adjust": False,
}


def get_option(key: str, options: dict[str, Any]) -> Any:
    """Get an option value from options dict or fall back to default.

    Args:
        key: The option key to retrieve.
        options: Dictionary of user-provided options.

    Returns:
        The value from options dict if present, otherwise the default value.
    """
    return options.get(key, default_opts.get(key))


def columnize(
    array: Union[list[Any], tuple[Any, ...]],
    displaywidth: int = 80,
    colsep: str = "  ",
    arrange_vertical: bool = True,
    ljust: bool = True,
    lineprefix: str = "",
    opts: Optional[dict[str, Any]] = None,
) -> str:
    """Format a list of strings as a compact set of columns.

    Arranges the strings either vertically (top-to-bottom, left-to-right)
    or horizontally (left-to-right, top-to-bottom) within the given display width.
    Each column is only as wide as necessary.

    Args:
        array: List or tuple of strings to format into columns.
        displaywidth: Maximum width for the output in characters. Defaults to 80.
        colsep: String separator between columns. Defaults to "  ".
        arrange_vertical: If True, arrange items vertically (top-to-bottom).
            If False, arrange horizontally (left-to-right). Defaults to True.
        ljust: If True, left-justify text in columns. If False, right-justify.
            Defaults to True.
        lineprefix: String to prepend to each line. Defaults to "".
        opts: Optional dict of additional formatting options. Defaults to None.

    Returns:
        Formatted string with items arranged in columns.

    Raises:
        TypeError: If array is not a list or tuple.

    Examples:
        For a line width of 4 characters (arranged vertically):
            ['1', '2,', '3', '4'] => '1  3\\n2  4\\n'

        Or arranged horizontally:
            ['1', '2,', '3', '4'] => '1  2\\n3  4\\n'
    """
    if opts is None:
        opts = {}
    if not isinstance(array, (list, tuple)):
        raise TypeError("array needs to be an instance of a list or a tuple")

    if len(opts.keys()) > 0:
        o = {key: get_option(key, opts) for key in default_opts}
        if o["arrange_array"]:
            o.update(
                {
                    "array_prefix": "[",
                    "lineprefix": " ",
                    "linesuffix": ",\n",
                    "array_suffix": "]\n",
                    "colsep": ", ",
                    "arrange_vertical": False,
                }
            )

    else:
        o = default_opts.copy()
        o.update(
            {
                "displaywidth": displaywidth,
                "colsep": colsep,
                "arrange_vertical": arrange_vertical,
                "ljust": ljust,
                "lineprefix": lineprefix,
            }
        )

    # if o['ljust'] is None:
    #     o['ljust'] = !(list.all?{|datum| datum.kind_of?(Numeric)})

    array = [o["colfmt"] % i for i in array] if o["colfmt"] else [str(i) for i in array]

    # Some degenerate cases
    size = len(array)
    if size == 0:
        return "<empty>\n"
    elif size == 1:
        return o["array_prefix"] + str(array[0]) + o["array_suffix"] + "\n"

    if o["displaywidth"] - len(o["lineprefix"]) < 4:
        o["displaywidth"] = len(o["lineprefix"]) + 4
    else:
        o["displaywidth"] -= len(o["lineprefix"])

    o["displaywidth"] = max(4, o["displaywidth"] - len(o["lineprefix"]))
    if o["arrange_vertical"]:

        def array_index(nrows, row, col):
            return nrows * col + row

        # Try every row count from 1 upwards
        for nrows in range(1, size):
            ncols = (size + nrows - 1) // nrows
            colwidths = []
            totwidth = -len(o["colsep"])
            for col in range(ncols):
                # get max column width for this column
                colwidth = 0
                for row in range(nrows):
                    i = array_index(nrows, row, col)
                    if i >= size:
                        break
                    x = array[i]
                    colwidth = max(colwidth, len(x))
                colwidths.append(colwidth)
                totwidth += colwidth + len(o["colsep"])
                if totwidth > o["displaywidth"]:
                    break
            if totwidth <= o["displaywidth"]:
                break
        # The smallest number of rows computed and the
        # max widths for each column has been obtained.
        # Now we just have to format each of the
        # rows.
        s = ""
        for row in range(nrows):
            texts = []
            for col in range(ncols):
                i = row + nrows * col
                x = "" if i >= size else array[i]
                texts.append(x)
            while texts and not texts[-1]:
                del texts[-1]
            for col in range(len(texts)):
                if o["ljust"]:
                    texts[col] = texts[col].ljust(colwidths[col])
                else:
                    texts[col] = texts[col].rjust(colwidths[col])
            s += o["lineprefix"] + o["colsep"].join(texts) + o["linesuffix"]
        return s
    else:

        def array_index(ncols, row, col):
            return ncols * (row - 1) + col

        # Try every column count from size downwards
        colwidths = []
        for ncols in range(size, 0, -1):
            # Try every row count from 1 upwards
            min_rows = (size + ncols - 1) // ncols
            nrows = min_rows - 1
            while nrows < size:
                nrows += 1
                rounded_size = nrows * ncols
                colwidths = []
                totwidth = -len(o["colsep"])
                for col in range(ncols):
                    # get max column width for this column
                    colwidth = 0
                    for row in range(1, nrows + 1):
                        i = array_index(ncols, row, col)
                        if i >= rounded_size:
                            break
                        elif i < size:
                            x = array[i]
                            colwidth = max(colwidth, len(x))
                    colwidths.append(colwidth)
                    totwidth += colwidth + len(o["colsep"])
                    if totwidth >= o["displaywidth"]:
                        break
                if totwidth <= o["displaywidth"] and i >= rounded_size - 1:
                    # Found the right nrows and ncols
                    # print "right nrows and ncols"
                    nrows = row
                    break
                elif totwidth >= o["displaywidth"]:
                    # print "reduce ncols", ncols
                    # Need to reduce ncols
                    break
            if totwidth <= o["displaywidth"] and i >= rounded_size - 1:
                break
        # The smallest number of rows computed and the
        # max widths for each column has been obtained.
        # Now we just have to format each of the
        # rows.
        s = ""
        prefix = o["array_prefix"] if len(o["array_prefix"]) != 0 else o["lineprefix"]
        for row in range(1, nrows + 1):
            texts = []
            for col in range(ncols):
                i = array_index(ncols, row, col)
                if i >= size:
                    break
                else:
                    x = array[i]
                texts.append(x)
            for col in range(len(texts)):
                if o["ljust"]:
                    texts[col] = texts[col].ljust(colwidths[col])
                else:
                    texts[col] = texts[col].rjust(colwidths[col])
            s += prefix + o["colsep"].join(texts) + o["linesuffix"]
            prefix = o["lineprefix"]
        if o["arrange_array"]:
            colsep = o["colsep"].rstrip()
            colsep_pos = -(len(colsep) + 1)
            if s[colsep_pos:] == colsep + "\n":
                s = s[:colsep_pos] + o["array_suffix"] + "\n"
        else:
            s += o["array_suffix"]
        return s
