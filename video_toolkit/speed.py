"""Roughly how long an encode will take.

Deliberately approximate. Encode speed swings by an order of magnitude between
codecs and again with resolution, so this is here to tell a two second job from
a four minute one — enough to decide whether interrupting someone with a
question is worth it — and not to predict either precisely.

The factors are realtime multiples measured on this machine: a clip of N
seconds takes about N/factor seconds to encode.
"""

from __future__ import annotations

# Realtime multiples, normalised to 1080p. Measured on this machine, then
# rounded down: underestimating is the harmful direction, because it is what
# decides whether someone is offered a way out of a long wait.
#
#   vp9 at 720p ran at 0.61x, which is 0.27x once scaled to 1080p
#   libx264 at 720p ran at 13.9x, which is 6.2x at 1080p
#   h264_videotoolbox at 720p ran at 11.2x, which is 5.0x at 1080p
_ENCODE_SPEED = {
    "libx264": 5.0,
    "h264_videotoolbox": 4.0,
    "libx265": 1.5,
    "hevc_videotoolbox": 3.0,
    "libvpx-vp9": 0.25,
    "libvpx": 0.8,
    "libsvtav1": 0.5,
}

# The factors above were measured at roughly 1080p; anything larger costs more.
_REFERENCE_PIXELS = 1920 * 1080

# Below this, asking costs more attention than the wait does.
SLOW_ENOUGH_TO_ASK = 20.0


def estimate_encode_seconds(
    duration: float | None,
    encoder: str,
    pixels: int | None = None,
) -> float | None:
    """About how long encoding `duration` seconds with `encoder` will take."""
    if not duration or duration <= 0:
        return None
    speed = _ENCODE_SPEED.get(encoder)
    if speed is None:
        return None

    if pixels and pixels > 0:
        speed *= _REFERENCE_PIXELS / pixels

    return duration / speed


def is_slow(seconds: float | None) -> bool:
    """Whether a job is worth offering to put in the background.

    An unknown length counts as slow: downloads have no predictable duration,
    and those are exactly the ones worth getting out of the way.
    """
    if seconds is None:
        return True
    return seconds > SLOW_ENOUGH_TO_ASK


def describe_wait(seconds: float | None) -> str:
    """A wait, phrased the way someone would say it out loud."""
    if seconds is None:
        return "an unknown time"
    if seconds < 15:
        return "a few seconds"
    if seconds < 60:
        return "under a minute"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"about {minutes} minute{'s' if minutes != 1 else ''}"
    hours = seconds / 3600
    return f"about {hours:.1f} hours"
