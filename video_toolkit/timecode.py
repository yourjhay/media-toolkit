"""Reading and writing times the way people type them."""

from __future__ import annotations

_MAX_PARTS = 3


def parse_timecode(text: str) -> float:
    """Seconds from "90", "1:30" or "1:02:03".

    Minutes and seconds must be under sixty when written as parts: "1:90" is
    far more likely a typo for "2:30" than a deliberate ninety seconds, and
    guessing wrong would trim the wrong piece of someone's video.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("No time given")

    parts = text.split(":")
    if len(parts) > _MAX_PARTS or any(not part.strip() for part in parts):
        raise ValueError(f"Cannot read {text!r} as a time")

    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        raise ValueError(f"Cannot read {text!r} as a time") from None

    if any(number < 0 for number in numbers):
        raise ValueError("A time cannot be negative")

    if len(numbers) > 1 and any(number >= 60 for number in numbers[1:]):
        raise ValueError(f"{text!r} has a part of sixty or more; did you mean something else?")

    seconds = 0.0
    for number in numbers:
        seconds = seconds * 60 + number
    return seconds


def format_timecode(seconds: float) -> str:
    """Seconds as m:ss, or h:mm:ss once there is an hour to show."""
    seconds = int(max(0, seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def validate_range(
    start: float,
    end: float | None,
    duration: float | None,
) -> tuple[float, float]:
    """A start and end that make sense for a clip of `duration` seconds."""
    if duration is not None and start >= duration:
        raise ValueError(
            f"The clip is only {format_timecode(duration)} long, "
            f"so it cannot start at {format_timecode(start)}"
        )

    if end is None:
        if duration is None:
            raise ValueError("Give an end time, or a clip whose length is known")
        end = duration

    if duration is not None:
        end = min(end, duration)

    if end <= start:
        raise ValueError("The end must come after the start")

    return float(start), float(end)
