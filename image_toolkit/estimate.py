"""Predicting output size before anything is written.

For the compressor the answer is arithmetic: the target *is* the estimate.
For a quality setting there is no formula — JPEG and WebP size depends on the
picture — so the real file is encoded at a handful of quality anchors once and
everything in between is interpolated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

# Clustered at the top because the curve steepens sharply there: on a 12MP
# photo q95 is 3.2 MB and q100 is 5.9 MB.
QUALITY_ANCHORS: tuple[int, ...] = (10, 30, 50, 70, 85, 90, 95, 100)


@dataclass
class SizeModel:
    """Measured sizes at a few qualities, interpolated in between."""

    anchors: dict[int, int]
    source_bytes: int
    sample_name: str | None = None
    scaled: bool = False

    def __post_init__(self) -> None:
        if not self.anchors:
            raise ValueError("a size model needs at least one measured anchor")

    def estimate(self, quality: int) -> int:
        points = sorted(self.anchors.items())
        if quality <= points[0][0]:
            return points[0][1]
        if quality >= points[-1][0]:
            return points[-1][1]
        for (low_q, low_bytes), (high_q, high_bytes) in zip(points, points[1:]):
            if low_q <= quality <= high_q:
                span = high_q - low_q
                if span == 0:
                    return low_bytes
                ratio = (quality - low_q) / span
                return round(low_bytes + (high_bytes - low_bytes) * ratio)
        raise AssertionError("unreachable")


def build_quality_model(
    encode: Callable[[int], int],
    source_bytes: int,
    anchors: Iterable[int] = QUALITY_ANCHORS,
    batch_source_bytes: int | None = None,
    sample_name: str | None = None,
) -> SizeModel:
    """Measure `encode` at each anchor, optionally scaled up to a whole batch.

    Only one file is ever encoded. For a batch its size ratio is applied to the
    total, which assumes the rest of the photos are broadly similar — true of a
    camera roll, and the estimate is labelled as approximate either way.
    """
    anchors = tuple(anchors)
    measured = {quality: encode(quality) for quality in anchors}

    scaled = batch_source_bytes is not None and batch_source_bytes != source_bytes
    if batch_source_bytes is not None and source_bytes > 0:
        factor = batch_source_bytes / source_bytes
        measured = {q: round(size * factor) for q, size in measured.items()}
        total = batch_source_bytes
    else:
        total = source_bytes

    return SizeModel(measured, total, sample_name=sample_name, scaled=scaled)


def compress_target(source_bytes: int, reduce_pct: float) -> int:
    """The byte budget a `reduce_pct` percent reduction asks for."""
    if not 0 < reduce_pct < 100:
        raise ValueError(f"reduce_pct must be between 1 and 99, got {reduce_pct}")
    return int(source_bytes * (1 - reduce_pct / 100))
