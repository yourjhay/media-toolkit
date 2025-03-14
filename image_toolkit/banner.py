"""The startup banner.

Pure strings and colour maths, no console, so the art's alignment is checked
in tests rather than by squinting at a terminal.

Two hand-drawn fonts are kept here. The widest one that fits the terminal is
used; below the compact font's width the box-drawing rows would wrap into
nonsense, so a plain title is shown instead.
"""

from __future__ import annotations

RGB = tuple[int, int, int]

PLAIN_TITLE = "IMG TOOLKIT"
BYLINE = "by rj"
SUBTITLE = "HEIC → JPG/PNG   ·   JPG/PNG → WebP   ·   compress"

GRADIENT_START: RGB = (0, 214, 170)   # teal
GRADIENT_END: RGB = (110, 130, 255)   # periwinkle

# Six-row block capitals.
_BIG: dict[str, tuple[str, ...]] = {
    "I": (
        "██╗",
        "██║",
        "██║",
        "██║",
        "██║",
        "╚═╝",
    ),
    "M": (
        "███╗   ███╗",
        "████╗ ████║",
        "██╔████╔██║",
        "██║╚██╔╝██║",
        "██║ ╚═╝ ██║",
        "╚═╝     ╚═╝",
    ),
    "G": (
        " ██████╗ ",
        "██╔════╝ ",
        "██║  ███╗",
        "██║   ██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ),
    "T": (
        "████████╗",
        "╚══██╔══╝",
        "   ██║   ",
        "   ██║   ",
        "   ██║   ",
        "   ╚═╝   ",
    ),
    "O": (
        " ██████╗ ",
        "██╔═══██╗",
        "██║   ██║",
        "██║   ██║",
        "╚██████╔╝",
        " ╚═════╝ ",
    ),
    "L": (
        "██╗     ",
        "██║     ",
        "██║     ",
        "██║     ",
        "███████╗",
        "╚══════╝",
    ),
    "K": (
        "██╗  ██╗",
        "██║ ██╔╝",
        "█████╔╝ ",
        "██╔═██╗ ",
        "██║  ██╗",
        "╚═╝  ╚═╝",
    ),
    " ": (
        "   ",
        "   ",
        "   ",
        "   ",
        "   ",
        "   ",
    ),
}

# Three-row box-drawing capitals, for terminals too narrow for the big font.
_MEDIUM: dict[str, tuple[str, ...]] = {
    "I": ("╦", "║", "╩"),
    "M": ("╔╦╗", "║║║", "╩ ╩"),
    "G": ("╔═╗", "║ ╦", "╚═╝"),
    "T": ("╔╦╗", " ║ ", " ╩ "),
    "O": ("╔═╗", "║ ║", "╚═╝"),
    "L": ("╦  ", "║  ", "╩═╝"),
    "K": ("╦╔═", "╠╩╗", "╩ ╩"),
    " ": ("  ", "  ", "  "),
}


def _render(text: str, glyphs: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Lay the glyphs out side by side into one block of rows."""
    height = len(next(iter(glyphs.values())))
    return tuple("".join(glyphs[char][row] for char in text) for row in range(height))


_BIG_ART = _render(PLAIN_TITLE, _BIG)
_MEDIUM_ART = _render(PLAIN_TITLE, _MEDIUM)

BIG_WIDTH = len(_BIG_ART[0])
MEDIUM_WIDTH = len(_MEDIUM_ART[0])


def glyph_table() -> dict[str, dict[str, tuple[str, ...]]]:
    """The fonts, exposed so tests can check them for drift."""
    return {"big": _BIG, "medium": _MEDIUM}


def _art_for(width: int) -> tuple[tuple[str, ...], int]:
    if width >= BIG_WIDTH:
        return _BIG_ART, BIG_WIDTH
    if width >= MEDIUM_WIDTH:
        return _MEDIUM_ART, MEDIUM_WIDTH
    return (PLAIN_TITLE,), len(PLAIN_TITLE)


def banner_lines(width: int) -> list[str]:
    """The banner centred in, and padded out to, a terminal `width` wide.

    Every line is exactly `width` characters so the gradient can run edge to
    edge without leaving gaps at the ends of the shorter rows.
    """
    art, art_width = _art_for(width)
    left = max(0, (width - art_width) // 2)
    lines = [(" " * left + row).ljust(width)[:width] for row in art]
    byline = (" " * left + BYLINE.rjust(art_width)).ljust(width)[:width]
    return [*lines, byline]


def gradient_colors(steps: int, start: RGB, end: RGB) -> list[RGB]:
    """`steps` colours interpolated from `start` to `end`, inclusive."""
    if steps < 0:
        raise ValueError(f"steps must not be negative, got {steps}")
    if steps == 0:
        return []
    if steps == 1:
        return [start]
    return [
        tuple(round(a + (b - a) * i / (steps - 1)) for a, b in zip(start, end))  # type: ignore[misc]
        for i in range(steps)
    ]


def subtitle_for(width: int) -> str | None:
    """The tagline, or None when the terminal is too narrow to hold it.

    Truncating it would cut mid-word, which looks like a rendering bug.
    """
    return SUBTITLE if width >= len(SUBTITLE) else None
