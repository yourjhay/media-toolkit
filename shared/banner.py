"""The startup banner.

Pure strings and colour maths, no console, so the art's alignment is checked
in tests rather than by squinting at a terminal.

Two hand-drawn fonts are kept here. The widest one that fits the terminal is
used; below the compact font's width the box-drawing rows would wrap into
nonsense, so a plain title is shown instead.
"""

from __future__ import annotations

RGB = tuple[int, int, int]


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
    "V": (
        "██╗   ██╗",
        "██║   ██║",
        "██║   ██║",
        "╚██╗ ██╔╝",
        " ╚████╔╝ ",
        "  ╚═══╝  ",
    ),
    "D": (
        "██████╗ ",
        "██╔══██╗",
        "██║  ██║",
        "██║  ██║",
        "██████╔╝",
        "╚═════╝ ",
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
    "V": ("╦  ╦", "╚╗╔╝", " ╚╝ "),
    "D": ("╔╦╗", " ║║", "═╩╝"),
    " ": ("  ", "  ", "  "),
}


class MissingGlyph(Exception):
    """The font has no drawing for one of the title's letters."""


def _render(text: str, glyphs: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Lay the glyphs out side by side into one block of rows."""
    missing = {char for char in text if char not in glyphs}
    if missing:
        raise MissingGlyph(f"no glyph for {sorted(missing)} in this font")
    height = len(next(iter(glyphs.values())))
    return tuple("".join(glyphs[char][row] for char in text) for row in range(height))


def big_width(title: str) -> int:
    return len(_render(title, _BIG)[0])


def medium_width(title: str) -> int:
    return len(_render(title, _MEDIUM)[0])


def glyph_table() -> dict[str, dict[str, tuple[str, ...]]]:
    """The fonts, exposed so tests can check them for drift."""
    return {"big": _BIG, "medium": _MEDIUM}


def _art_for(width: int, title: str) -> tuple[tuple[str, ...], int]:
    if width >= big_width(title):
        return _render(title, _BIG), big_width(title)
    if width >= medium_width(title):
        return _render(title, _MEDIUM), medium_width(title)
    return (title,), len(title)


def banner_lines(width: int, title: str) -> list[str]:
    """The banner centred in, and padded out to, a terminal `width` wide.

    Every line is exactly `width` characters so the gradient can run edge to
    edge without leaving gaps at the ends of the shorter rows.
    """
    art, art_width = _art_for(width, title)
    left = max(0, (width - art_width) // 2)
    return [(" " * left + row).ljust(width)[:width] for row in art]


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


def subtitle_for(width: int, subtitle: str) -> str | None:
    """The tagline, or None when the terminal is too narrow to hold it.

    Truncating it would cut mid-word, which looks like a rendering bug.
    """
    return subtitle if width >= len(subtitle) else None
