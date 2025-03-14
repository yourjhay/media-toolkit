"""What the video toolkit can do, and how its menu presents it."""

from __future__ import annotations

from shared.menu import MenuItem

from .formats import AUDIO, MODES, VIDEO

QUIT = "__quit__"

OPERATIONS: dict[str, str] = {
    "download": "Download a video",
    "audio": "Download the audio only",
    "formats": "List the available formats",
    "convert": "Change a video's format",
    "compress": "Compress a video to a target size",
    "trim": "Keep only part of a video",
}

# Looks only; no file is written.
READ_ONLY = frozenset({"formats"})

# Work on a file already on this machine, rather than on a link.
LOCAL = frozenset({"convert", "compress", "trim"})

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".flv", ".wmv", ".mpg", ".mpeg"}

SIZE_PRESETS = (
    ("8 MB", 8 * 1024 * 1024),
    ("25 MB", 25 * 1024 * 1024),
    ("50 MB", 50 * 1024 * 1024),
    ("100 MB", 100 * 1024 * 1024),
)

# 4K and 1440p are listed even though "best available" would reach them
# anyway: a menu that stops at 1080p reads as a tool that stops there too.
QUALITY_PRESETS = (
    ("Best available", None),
    ("Up to 2160p  (4K)", 2160),
    ("Up to 1440p  (2K)", 1440),
    ("Up to 1080p", 1080),
    ("Up to 720p", 720),
    ("Up to 480p", 480),
)


def menu_items() -> list[MenuItem]:
    return [
        MenuItem("download", "Download", "video, best quality", "#00d6aa"),
        MenuItem("audio", "Audio only", "strip the picture", "#4aa8ff"),
        MenuItem("formats", "List formats", "see what is on offer", "#c77dff"),
        MenuItem("convert", "Convert", "change the container", "#f0a02a"),
        MenuItem("compress", "Compress", "hit a target size", "#7ee787"),
        MenuItem("trim", "Trim", "keep part of a clip", "#ff8fa3"),
        MenuItem(QUIT, "Quit", "leave the toolkit", "#8b949e"),
    ]


_NOUNS = {VIDEO: ("video", "videos"), AUDIO: ("audio track", "audio tracks")}


def download_noun(mode: str, count: int) -> str:
    """How to describe what is about to be fetched.

    Audio mode discards the picture entirely, so calling the result a video
    describes the source rather than what the user ends up with.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    singular, plural = _NOUNS[mode]
    return f"{count} {singular if count == 1 else plural}"
