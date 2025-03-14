"""What the video toolkit can do, and how its menu presents it."""

from __future__ import annotations

from shared.menu import MenuItem

QUIT = "__quit__"

OPERATIONS: dict[str, str] = {
    "download": "Download a video",
    "audio": "Download the audio only",
    "formats": "List the available formats",
}

# Looks only; no file is written.
READ_ONLY = frozenset({"formats"})

QUALITY_PRESETS = (
    ("Best available", None),
    ("Up to 1080p", 1080),
    ("Up to 720p", 720),
    ("Up to 480p", 480),
)


def menu_items() -> list[MenuItem]:
    return [
        MenuItem("download", "Download", "video, best quality", "#00d6aa"),
        MenuItem("audio", "Audio only", "strip the picture", "#4aa8ff"),
        MenuItem("formats", "List formats", "see what is on offer", "#c77dff"),
        MenuItem(QUIT, "Quit", "leave the toolkit", "#8b949e"),
    ]
