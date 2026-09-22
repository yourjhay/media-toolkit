"""Turning a drawing described as shapes into one made of pixels.

A vector has no size of its own in the way a photograph does, so the awkward
part is deciding how large to render it. That decision is made here, away from
the renderer, because the file's own answer is often absent, in units, or a
percentage of something it knows nothing about.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

Size = tuple[float, float]

# CSS absolute units, in pixels. Anything relative (%, em) depends on context
# this file does not have, so those fall through to the viewBox instead.
_UNITS = {"px": 1.0, "pt": 96 / 72, "pc": 16.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4}
_LENGTH = re.compile(r"^\s*([0-9.]+)\s*([a-z%]*)\s*$", re.I)


def _length(value: str | None) -> float | None:
    if not value:
        return None
    match = _LENGTH.match(value)
    if not match:
        return None
    number, unit = match.groups()
    try:
        amount = float(number)
    except ValueError:
        return None
    if not unit:
        return amount
    factor = _UNITS.get(unit.lower())
    return amount * factor if factor else None


def intrinsic_size(data: bytes) -> Size | None:
    """The size the file claims for itself, in pixels, if it claims one."""
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return None

    width = _length(root.get("width"))
    height = _length(root.get("height"))
    if width and height:
        return width, height

    box = (root.get("viewBox") or "").replace(",", " ").split()
    if len(box) == 4:
        try:
            return abs(float(box[2])), abs(float(box[3]))
        except ValueError:
            return None
    return None


def render_size(
    intrinsic: Size | None,
    scale: float = 1.0,
    width: int | None = None,
) -> tuple[int | None, int | None]:
    """The pixel size to render at.

    An exact width wins over a scale, since it is the more specific request.
    A None means "let the renderer decide", which it can do for a width but
    not for a scale with nothing to multiply.
    """
    if width:
        if not intrinsic:
            # Nothing declares an aspect ratio, and the renderer will not take
            # a width on its own, so a square is the only assumption available.
            return max(1, width), max(1, width)
        original_width, original_height = intrinsic
        height = round(width * original_height / original_width) if original_width else None
        return max(1, width), max(1, height) if height else None

    if not intrinsic:
        return None, None

    return (
        max(1, round(intrinsic[0] * scale)),
        max(1, round(intrinsic[1] * scale)),
    )


def read_intrinsic_size(path: Path) -> Size | None:
    try:
        return intrinsic_size(Path(path).read_bytes())
    except OSError:
        return None
