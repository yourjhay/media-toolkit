"""The decisions a run needs, separated from the prompts that collect them.

Keeping this free of questionary means the whole planning layer is testable,
and a flag-driven CLI could reuse it unchanged.
"""

from __future__ import annotations

import re
from functools import partial
from pathlib import Path
from typing import Callable


from .core import compress, convert_heic, convert_to_webp
from .discovery import HEIC_EXTS, RASTER_EXTS
from .jobs import Operation
from .menu import MenuItem

OUTPUT_DIRNAME = "converted"

# A real value, never None: questionary falls back to a Choice's title when
# its value is None, which would make this come back as the string "Quit".
QUIT = "__quit__"

OPERATIONS: dict[str, str] = {
    "heic": "HEIC / HEIF  →  JPG or PNG",
    "webp": "JPG / PNG    →  WebP",
    "compress": "Compress JPG / PNG to a target size",
}

_EXTENSIONS: dict[str, set[str]] = {
    "heic": HEIC_EXTS,
    "webp": RASTER_EXTS,
    "compress": RASTER_EXTS,
}

_FUNCTIONS = {
    "heic": convert_heic,
    "webp": convert_to_webp,
    "compress": compress,
}


def extensions_for(operation: str) -> set[str]:
    try:
        return _EXTENSIONS[operation]
    except KeyError:
        raise ValueError(f"Unknown operation: {operation!r}") from None


def default_output_dir(source: Path) -> Path:
    """Where output lands unless the user says otherwise.

    Always a sibling folder, never the source folder itself — originals are
    not overwritten by accident.
    """
    source = Path(source)
    base = source.parent if source.is_file() else source
    return base / OUTPUT_DIRNAME


def human_bytes(size: int | float) -> str:
    sign = "-" if size < 0 else ""
    size = abs(size)
    if size < 1024:
        return f"{sign}{int(size)} B"
    for unit in ("KB", "MB", "GB"):
        size /= 1024
        if size < 1024 or unit == "GB":
            return f"{sign}{size:.1f} {unit}"
    raise AssertionError("unreachable")


def make_operation(
    operation: str,
    dest_dir: Path,
    outputs: dict[Path, Path] | None = None,
    **options,
) -> Operation:
    """Bind an operation and its settings into a one-argument callable.

    `outputs` maps each source to the exact path it should be written to, as
    produced by `assign_output_paths`. Without it each file derives its own
    name, which is fine when nothing collides.
    """
    try:
        func = _FUNCTIONS[operation]
    except KeyError:
        raise ValueError(f"Unknown operation: {operation!r}") from None

    dest_dir = Path(dest_dir)
    if outputs is None:
        return partial(func, dest_dir=dest_dir, **options)

    def run(src: Path):
        return func(src, dest_dir=dest_dir, out_path=outputs.get(src), **options)

    return run


def menu_items() -> list[MenuItem]:
    """The main menu as cards: every operation, then quit."""
    return [
        MenuItem("heic", "HEIC / HEIF", "→ JPG or PNG", "#00d6aa"),
        MenuItem("webp", "JPG / PNG", "→ WebP", "#4aa8ff"),
        MenuItem("compress", "Compress", "shrink to a target size", "#f0a02a"),
        MenuItem(QUIT, "Quit", "leave the toolkit", "#8b949e"),
    ]


_QUOTE_PAIRS = (("'", "'"), ('"', '"'))


def clean_path_input(raw: str) -> Path:
    """Turn what a person actually types at a path prompt into a Path.

    Handles the three ways a perfectly valid path arrives broken:
    tab completion appends a trailing space, copied paths come wrapped in
    quotes, and dragging a file into a macOS terminal backslash-escapes the
    spaces. A quoted path is taken literally, since the quotes already did
    the escaping.
    """
    text = raw.strip()

    quoted = False
    for opening, closing in _QUOTE_PAIRS:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            text, quoted = text[1:-1], True
            break

    if not quoted:
        # Undo shell-style escaping: "my\ photos" -> "my photos".
        text = re.sub(r"\\(.)", r"\1", text).strip()

    if not text:
        raise ValueError("No path given")

    return Path(text).expanduser()


def size_change_row(bytes_saved: int) -> tuple[str, str]:
    """Label and value for the summary's size line.

    Conversions do not always shrink a file — HEIC out-compresses JPEG, so
    HEIC to JPG routinely grows one. Reporting that as a negative saving reads
    like a bug, so the label flips instead.
    """
    if bytes_saved < 0:
        return "Size increase", human_bytes(-bytes_saved)
    return "Space saved", human_bytes(bytes_saved)


def format_estimate(estimated_bytes: int, source_bytes: int) -> str:
    """The live hint shown beside a quality or percentage prompt."""
    head = f"≈ {human_bytes(estimated_bytes)}"
    if source_bytes <= 0:
        return head

    change = round((estimated_bytes - source_bytes) / source_bytes * 100)
    if change == 0:
        delta = "same size"
    else:
        delta = f"{change:+d}%"
    return f"{head}  (from {human_bytes(source_bytes)}, {delta})"


def median_by_size(paths: list[Path]) -> Path | None:
    """The middling file of a batch, used as the sample for size estimates.

    Median rather than first or largest: one panorama among a hundred snapshots
    would otherwise set the expectation for all of them.
    """
    if not paths:
        return None
    ordered = sorted(paths, key=lambda p: p.stat().st_size)
    return ordered[len(ordered) // 2]


def output_name(operation: str, src: Path, fmt: str | None = None) -> str:
    """What one source file is called once the operation is done with it."""
    if operation == "heic":
        return f"{src.stem}.{(fmt or 'jpg').lower().lstrip('.')}"
    if operation == "webp":
        return f"{src.stem}.webp"
    if operation == "compress":
        return src.name  # same format in, same out
    raise ValueError(f"Unknown operation: {operation!r}")


def assign_output_paths(
    files: list[Path],
    dest_dir: Path,
    name_for: Callable[[Path], str],
) -> dict[Path, Path]:
    """Give every source a distinct output path inside one flat folder.

    A recursive run flattens subfolders, so `a/photo.jpg` and `b/photo.jpg`
    both want `photo.webp`. The first claim wins and later ones are numbered,
    `photo-2.webp` and so on, which keeps a whole tree in one folder without
    one file quietly replacing another.

    Names are compared case-insensitively, because macOS filesystems treat
    `Photo.webp` and `photo.webp` as the same file.
    """
    dest_dir = Path(dest_dir)
    taken: set[str] = set()
    assigned: dict[Path, Path] = {}

    for src in files:
        name = name_for(src)
        stem, dot, ext = name.rpartition(".")
        if not dot:
            stem, ext = name, ""

        candidate = name
        counter = 1
        while candidate.casefold() in taken:
            counter += 1
            candidate = f"{stem}-{counter}.{ext}" if ext else f"{stem}-{counter}"

        taken.add(candidate.casefold())
        assigned[src] = dest_dir / candidate

    return assigned
