"""Turning numbers into something a person can read."""

from __future__ import annotations


def human_bytes(size: int | float) -> str:
    sign = "-" if size < 0 else ""
    size = abs(size)
    if size < 1024:
        return f"{sign}{int(size)} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{sign}{size:.1f} {unit}"
    raise AssertionError("unreachable")


def human_duration(seconds: float | None) -> str:
    """Seconds as h:mm:ss, or m:ss when under an hour."""
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def size_change_row(bytes_saved: int) -> tuple[str, str]:
    """Label and value for a summary's size line.

    Operations do not always shrink a file — HEIC out-compresses JPEG, so
    converting to JPG routinely grows one. Reporting that as a negative saving
    reads like a bug, so the label flips instead.
    """
    if bytes_saved < 0:
        return "Size increase", human_bytes(-bytes_saved)
    return "Space saved", human_bytes(bytes_saved)
