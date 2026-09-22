"""The video operations, end to end: look at the file, decide, run ffmpeg."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from shared.format import human_bytes

from .bitrate import reencode_bitrate, target_bitrate
from .containers import plan_conversion
from .media import probe_media
from .operations import (
    FAILED,
    OK,
    OVER,
    SKIPPED,
    EncodeResult,
    build_compress_args,
    build_convert_args,
    build_trim_args,
    run_ffmpeg,
)
from .timecode import format_timecode, validate_range

DEFAULT_AUDIO_BITRATE = 128_000


def _guard(src: Path, out: Path, overwrite: bool) -> EncodeResult | None:
    """The checks every operation shares, before anything is written."""
    if out.resolve() == src.resolve():
        return EncodeResult(src, None, FAILED, src.stat().st_size, 0,
                            "refusing to write over the source; choose another folder")
    if out.exists() and not overwrite:
        return EncodeResult(src, out, SKIPPED, src.stat().st_size,
                            out.stat().st_size, "output already exists")
    return None


def _finish(src: Path, out: Path, ok: bool, message: str, detail: str,
            lossless: bool) -> EncodeResult:
    source_bytes = src.stat().st_size
    if not ok:
        return EncodeResult(src, None, FAILED, source_bytes, 0, message)
    if not out.exists():
        return EncodeResult(src, None, FAILED, source_bytes, 0,
                            f"ffmpeg reported success but {out.name} is not there")
    return EncodeResult(src, out, OK, source_bytes, out.stat().st_size, detail, lossless)


def convert_video(
    src: Path,
    dest_dir: Path,
    target_ext: str,
    overwrite: bool = False,
    hardware: bool = True,
    force_video_encode: bool = False,
    on_progress: Callable | None = None,
    probe: Callable | None = None,
    runner: Callable | None = None,
    on_start: Callable | None = None,
) -> EncodeResult:
    """Put the file into another container, repackaging where possible."""
    src, dest_dir = Path(src), Path(dest_dir)
    target = target_ext.lower().lstrip(".")
    out = dest_dir / f"{src.stem}.{target}"

    blocked = _guard(src, out, overwrite)
    if blocked is not None:
        return blocked

    info = (probe or probe_media)(src)
    if info.error:
        return EncodeResult(src, None, FAILED, src.stat().st_size, 0, info.error)

    try:
        plan = plan_conversion(
            info.video_codec, info.audio_codec, target,
            hardware=hardware, force_video_encode=force_video_encode,
        )
    except ValueError as exc:
        return EncodeResult(src, None, FAILED, src.stat().st_size, 0, str(exc))

    dest_dir.mkdir(parents=True, exist_ok=True)
    ok, message = run_ffmpeg(
        build_convert_args(src, out, plan, reencode_bitrate(info.video_bitrate)),
        info.duration, on_progress, runner, on_start,
    )
    return _finish(src, out, ok, message, plan.reason, plan.lossless)


def compress_video(
    src: Path,
    dest_dir: Path,
    target_bytes: int,
    overwrite: bool = False,
    hardware: bool = True,
    on_progress: Callable | None = None,
    probe: Callable | None = None,
    runner: Callable | None = None,
    on_start: Callable | None = None,
) -> EncodeResult:
    """Re-encode the file to land near a target size."""
    src, dest_dir = Path(src), Path(dest_dir)
    out = dest_dir / src.name

    blocked = _guard(src, out, overwrite)
    if blocked is not None:
        return blocked

    info = (probe or probe_media)(src)
    if info.error:
        return EncodeResult(src, None, FAILED, src.stat().st_size, 0, info.error)
    if not info.duration:
        return EncodeResult(src, None, FAILED, src.stat().st_size, 0,
                            "the clip's length is unknown, so no target size can be aimed for")

    audio_bitrate = min(info.audio_bitrate or DEFAULT_AUDIO_BITRATE, DEFAULT_AUDIO_BITRATE)
    if info.audio_codec is None:
        audio_bitrate = 0

    try:
        video_bitrate = target_bitrate(info.duration, target_bytes, audio_bitrate)
    except ValueError as exc:
        return EncodeResult(src, None, FAILED, src.stat().st_size, 0, str(exc))

    # Software encoding, deliberately. Apple's hardware encoder honours a
    # bitrate target loosely: on a 20 second clip asked for 1 MB it produced
    # 1.9 MB, where libx264 produced 995 KB. Speed is worth less than landing
    # near the size that was asked for.
    encoder = "libx264"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ok, message = run_ffmpeg(
        build_compress_args(src, out, video_bitrate, audio_bitrate or None, encoder),
        info.duration, on_progress, runner, on_start,
    )

    detail = f"{video_bitrate // 1000} kbps video via {encoder}"
    result = _finish(src, out, ok, message, detail, lossless=False)

    # One pass lands near the target, not exactly on it. Say so rather than
    # quietly handing back a file that is bigger than what was asked for.
    if result.status == OK and result.output_bytes > target_bytes:
        result.status = OVER
        result.detail = (
            f"came out {human_bytes(result.output_bytes)}, over the "
            f"{human_bytes(target_bytes)} asked for"
        )
    return result


def trim_video(
    src: Path,
    dest_dir: Path,
    start: float,
    end: float | None = None,
    precise: bool = False,
    overwrite: bool = False,
    hardware: bool = True,
    on_progress: Callable | None = None,
    probe: Callable | None = None,
    runner: Callable | None = None,
    on_start: Callable | None = None,
) -> EncodeResult:
    """Keep only the piece between `start` and `end`."""
    src, dest_dir = Path(src), Path(dest_dir)
    out = dest_dir / f"{src.stem}-clip{src.suffix}"

    blocked = _guard(src, out, overwrite)
    if blocked is not None:
        return blocked

    info = (probe or probe_media)(src)
    if info.error:
        return EncodeResult(src, None, FAILED, src.stat().st_size, 0, info.error)

    try:
        start, end = validate_range(start, end, info.duration)
    except ValueError as exc:
        return EncodeResult(src, None, FAILED, src.stat().st_size, 0, str(exc))

    encoder = "h264_videotoolbox" if hardware else "libx264"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ok, message = run_ffmpeg(
        build_trim_args(src, out, start, end, precise, encoder),
        end - start, on_progress, runner, on_start,
    )

    span = f"{format_timecode(start)} to {format_timecode(end)}"
    detail = (
        f"{span}, re-encoded for an exact cut"
        if precise
        else f"{span}, copied to the nearest keyframe"
    )
    result = _finish(src, out, ok, message, detail, lossless=not precise)

    # A stream copy has to begin at a keyframe, so the clip can come out longer
    # than asked for — by a lot, on a video with widely spaced keyframes. Say
    # what was actually produced rather than repeating what was requested.
    if result.status == OK and not precise:
        actual = (probe or probe_media)(out).duration
        wanted = end - start
        if actual and abs(actual - wanted) > 0.5:
            result.detail = (
                f"{span} asked for ({format_timecode(wanted)}), "
                f"{format_timecode(actual)} produced — the nearest keyframe. "
                f"Turn off the fast cut for an exact one."
            )
    return result
