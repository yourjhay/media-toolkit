"""Converting every video in a folder to one format.

The single-file conversion does the real work; this only finds the files,
decides up front which of them are worth converting, and runs them one after
another as a single job with a single progress figure.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .containers import playback_warning, plan_conversion
from .media import MediaInfo
from .operations import FAILED, OK, SKIPPED, EncodeResult
from .planning import VIDEO_SUFFIXES
from .speed import estimate_encode_seconds

# A repackage copies streams rather than encoding them: a second or so.
_REPACKAGE_SECONDS = 1.0


def find_videos(root: Path, recursive: bool = False, exclude: list[Path] | None = None) -> list[Path]:
    """The video files under `root`, sorted by path.

    Hidden files are skipped: macOS writes a `._clip.mov` beside every file
    copied to an external drive, and it has a video's name but none of its
    contents. Anything inside an `exclude` folder is skipped too, which keeps
    a re-run from converting the output of the last one.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"No such folder: {root}")

    # An output folder that holds the source folder is not excluded, or saving
    # beside the originals would exclude every one of them.
    inside = root.resolve()
    excluded = [
        bad for bad in (Path(p).resolve() for p in (exclude or []))
        if not inside.is_relative_to(bad)
    ]

    def wanted(path: Path) -> bool:
        if not path.is_file() or path.name.startswith("."):
            return False
        if path.suffix.lower() not in VIDEO_SUFFIXES:
            return False
        resolved = path.resolve()
        return not any(resolved.is_relative_to(bad) for bad in excluded)

    candidates = root.rglob("*") if recursive else root.glob("*")
    return sorted((p for p in candidates if wanted(p)), key=lambda p: str(p).lower())


def mirrored_dest(src: Path, root: Path, dest_dir: Path) -> Path:
    """The folder a file's output goes in: its own subfolder, under `dest_dir`.

    Mirroring the tree rather than flattening it means `a/clip.mov` and
    `b/clip.mov` never compete for the same output name.
    """
    return Path(dest_dir) / Path(src).parent.relative_to(root)


@dataclass
class BatchItem:
    info: MediaInfo
    dest_dir: Path
    lossless: bool
    estimate: float | None
    force_video_encode: bool = False

    @property
    def weight(self) -> float:
        """Its share of the batch's progress bar."""
        return self.estimate or _REPACKAGE_SECONDS


def _settled(info: MediaInfo, status: str, detail: str) -> EncodeResult:
    return EncodeResult(info.path, None, status, info.size_bytes, 0, detail)


def plan_batch(
    infos: list[MediaInfo],
    root: Path,
    dest_dir: Path,
    target_ext: str,
    force_awkward: bool = False,
    hardware: bool = True,
) -> tuple[list[BatchItem], list[EncodeResult]]:
    """Which files to convert, and the results already known without trying.

    `force_awkward` re-encodes only the files whose codec Apple's players will
    not open. Applying it to every file would re-encode H.264 that plays fine.
    """
    target = target_ext.lower().lstrip(".")
    items: list[BatchItem] = []
    settled: list[EncodeResult] = []
    claimed: set[str] = set()

    for info in infos:
        if info.error:
            settled.append(_settled(info, FAILED, info.error))
            continue

        force = force_awkward and playback_warning(info.video_codec, target) is not None
        try:
            plan = plan_conversion(
                info.video_codec, info.audio_codec, target,
                hardware=hardware, force_video_encode=force,
            )
        except ValueError as exc:
            settled.append(_settled(info, FAILED, str(exc)))
            continue

        if info.path.suffix.lower().lstrip(".") == target and plan.lossless:
            settled.append(_settled(info, SKIPPED, f"already {target}"))
            continue

        dest = mirrored_dest(info.path, root, dest_dir)
        out = dest / f"{info.path.stem}.{target}"
        # Compared case-insensitively: macOS treats Clip.mp4 and clip.mp4 as one.
        if str(out).lower() in claimed:
            settled.append(_settled(info, SKIPPED, f"another file here also becomes {out.name}"))
            continue
        claimed.add(str(out).lower())
        # Caught here as well as at conversion time, so the count asked about
        # before starting is the number that will actually be converted.
        if out.exists():
            settled.append(_settled(info, SKIPPED, f"{out.name} is already in the output folder"))
            continue

        if plan.video_lossless:
            estimate = _REPACKAGE_SECONDS
        else:
            pixels = info.width * info.height if info.width and info.height else None
            estimate = estimate_encode_seconds(info.duration, plan.video_encoder, pixels)

        items.append(BatchItem(info, dest, plan.lossless, estimate, force))

    return items, settled


def estimated_seconds(items: list[BatchItem]) -> float | None:
    """How long the whole batch should take; unknown if any one file is."""
    if any(item.estimate is None for item in items):
        return None
    return sum(item.estimate for item in items)


def run_batch(
    items: list[BatchItem],
    convert_one: Callable[[BatchItem, Callable[[float], None]], EncodeResult],
    report: Callable[[float], None] | None = None,
) -> list[EncodeResult]:
    """Convert each item in turn, reporting one percent for the whole batch.

    Each file's share of the bar is its estimated encode time, so a run of
    instant repackages does not race to 90% and then sit there while the one
    real encode at the end crawls through.
    """
    total = sum(item.weight for item in items) or 1.0
    done = 0.0
    results: list[EncodeResult] = []

    for item in items:
        def file_progress(percent: float, base: float = done, weight: float = item.weight) -> None:
            if report is not None:
                report((base + weight * percent / 100) / total * 100)

        try:
            results.append(convert_one(item, file_progress))
        except Exception as exc:
            # One bad file is that file's problem, not the batch's.
            results.append(_settled(item.info, FAILED, f"{type(exc).__name__}: {exc}"))

        done += item.weight
        if report is not None:
            report(done / total * 100)

    return results


@dataclass
class BatchResult:
    results: list[EncodeResult]
    # The folder everything went to, under the name the Jobs screen looks for.
    output: Path

    def of_status(self, status: str) -> list[EncodeResult]:
        return [result for result in self.results if result.status == status]

    @property
    def source_bytes(self) -> int:
        return sum(result.source_bytes for result in self.of_status(OK))

    @property
    def output_bytes(self) -> int:
        return sum(result.output_bytes for result in self.of_status(OK))
