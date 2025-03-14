"""Working out what size an image should become.

Pure arithmetic, so the awkward cases — aspect ratios that do not divide
evenly, limits larger than the image, percentages that would enlarge it — are
settled in tests rather than discovered on someone's photos.
"""

from __future__ import annotations

Size = tuple[int, int]


def target_size(
    original: Size,
    max_width: int | None = None,
    max_height: int | None = None,
    percent: float | None = None,
) -> Size:
    """The size `original` should be resized to.

    Give either a percentage or a bounding box, not both. The aspect ratio is
    always preserved, no side ever falls below one pixel, and the result is
    never larger than the original: enlarging invents detail that was never
    captured.
    """
    box = max_width is not None or max_height is not None
    if percent is not None and box:
        raise ValueError("give either a percentage or a width/height limit, not both")
    if percent is None and not box:
        raise ValueError("give a percentage or a width/height limit")

    width, height = original

    if percent is not None:
        if percent <= 0:
            raise ValueError(f"percent must be greater than 0, got {percent}")
        scale = percent / 100
    else:
        scales = []
        if max_width is not None:
            if max_width <= 0:
                raise ValueError(f"max_width must be greater than 0, got {max_width}")
            scales.append(max_width / width)
        if max_height is not None:
            if max_height <= 0:
                raise ValueError(f"max_height must be greater than 0, got {max_height}")
            scales.append(max_height / height)
        scale = min(scales)

    scale = min(scale, 1.0)
    return max(1, round(width * scale)), max(1, round(height * scale))
