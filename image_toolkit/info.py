"""Describing what the user just pointed at, before any work is planned."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .core import _load_upright
from .discovery import find_images


@dataclass
class FileInfo:
    path: Path
    name: str
    size_bytes: int
    location: Path
    dimensions: tuple[int, int] | None = None
    format: str | None = None
    error: str | None = None


@dataclass
class FolderInfo:
    path: Path
    name: str
    location: Path
    here_count: int
    here_bytes: int
    nested_count: int
    nested_bytes: int

    @property
    def total_count(self) -> int:
        return self.here_count + self.nested_count

    @property
    def total_bytes(self) -> int:
        return self.here_bytes + self.nested_bytes


def _describe_file(path: Path) -> FileInfo:
    info = FileInfo(
        path=path,
        name=path.name,
        size_bytes=path.stat().st_size,
        location=path.parent,
    )
    try:
        # Upright, so a rotated iPhone photo reports the shape you would see.
        img = _load_upright(path)
        info.dimensions = img.size
        info.format = img.format or path.suffix.lstrip(".").upper()
    except Exception as exc:
        info.error = f"{type(exc).__name__}: {exc}"
    return info


def _describe_folder(path: Path, extensions: set[str]) -> FolderInfo:
    everything = find_images(path, extensions, recursive=True)
    here = [p for p in everything if p.parent == path]
    nested = [p for p in everything if p.parent != path]
    return FolderInfo(
        path=path,
        name=path.name or str(path),
        location=path.parent,
        here_count=len(here),
        here_bytes=sum(p.stat().st_size for p in here),
        nested_count=len(nested),
        nested_bytes=sum(p.stat().st_size for p in nested),
    )


def inspect_source(path: Path, extensions: set[str]) -> FileInfo | FolderInfo:
    """Summarise a chosen source, whether it is one image or a folder of them."""
    path = Path(path)
    return _describe_file(path) if path.is_file() else _describe_folder(path, extensions)
