"""Making sense of paths as people actually type them."""

from __future__ import annotations

import re
from pathlib import Path

_QUOTE_PAIRS = (("'", "'"), ('"', '"'))


def clean_path_input(raw: str) -> Path:
    """Turn what a person types at a path prompt into a Path.

    Handles the three ways a perfectly valid path arrives broken: tab
    completion appends a trailing space, copied paths come wrapped in quotes,
    and dragging a file into a macOS terminal backslash-escapes the spaces. A
    quoted path is taken literally, since the quotes already did the escaping.
    """
    text = raw.strip()

    quoted = False
    for opening, closing in _QUOTE_PAIRS:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            text, quoted = text[1:-1], True
            break

    if not quoted:
        text = re.sub(r"\\(.)", r"\1", text).strip()

    if not text:
        raise ValueError("No path given")

    return Path(text).expanduser()
