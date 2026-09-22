"""Locating the image files an operation should run over."""

from __future__ import annotations

from pathlib import Path

HEIC_EXTS = {".heic", ".heif"}
RASTER_EXTS = {".jpg", ".jpeg", ".png"}
WEBP_EXTS = {".webp"}
SVG_EXTS = {".svg", ".svgz"}
ALL_IMAGE_EXTS = HEIC_EXTS | RASTER_EXTS | WEBP_EXTS | SVG_EXTS


def find_images(
    root: Path,
    extensions: set[str],
    recursive: bool = False,
    exclude: list[Path] | None = None,
) -> list[Path]:
    """Return the matching image files under `root`, sorted by name.

    `root` may be a single file or a directory. Matching is case-insensitive.
    Paths inside any `exclude` directory are skipped, which is what keeps a
    run from picking up the output of a previous run nested in the source.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"No such file or directory: {root}")

    wanted = {e.lower() for e in extensions}

    if root.is_file():
        return [root] if root.suffix.lower() in wanted else []

    excluded = [Path(p).resolve() for p in (exclude or [])]

    def is_excluded(path: Path) -> bool:
        resolved = path.resolve()
        return any(resolved.is_relative_to(bad) for bad in excluded)

    candidates = root.rglob("*") if recursive else root.glob("*")
    found = [
        p
        for p in candidates
        if p.is_file() and p.suffix.lower() in wanted and not is_excluded(p)
    ]
    return sorted(found, key=lambda p: (p.name.lower(), str(p)))
