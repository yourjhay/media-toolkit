"""Building and running the ffmpeg commands behind each video operation.

The command lines are assembled by plain functions so the flags can be checked
in tests without encoding anything. Running them is separate.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .containers import COPY, ConversionPlan
from .media import ProgressReader

OK = "ok"
SKIPPED = "skipped"
FAILED = "failed"
OVER = "over"

# Headroom above the average bitrate. Too tight starves detailed scenes; too
# loose and the peaks push the file past its target.
_MAXRATE_FACTOR = 1.5
_BUFSIZE_FACTOR = 2.0


def _base(src: Path) -> list[str]:
    return [
        "-hide_banner", "-loglevel", "error", "-nostats",
        "-progress", "pipe:1", "-y", "-i", str(src),
    ]


def _finish(args: list[str], out: Path) -> list[str]:
    if out.suffix.lower() == ".mp4":
        # Move the index to the front so the file can start playing before it
        # has finished downloading.
        args += ["-movflags", "+faststart"]
    args.append(str(out))
    return args


def build_convert_args(
    src: Path,
    out: Path,
    plan: ConversionPlan,
    video_bitrate: int | None = None,
) -> list[str]:
    args = _base(src)
    if plan.video is not None:
        args += ["-c:v", "copy" if plan.video == COPY else plan.video_encoder]
        if plan.video != COPY and video_bitrate:
            args += ["-b:v", str(video_bitrate)]
    if plan.audio is not None:
        args += ["-c:a", "copy" if plan.audio == COPY else plan.audio_encoder]
    return _finish(args, out)


def build_compress_args(
    src: Path,
    out: Path,
    video_bitrate: int,
    audio_bitrate: int | None,
    video_encoder: str,
) -> list[str]:
    args = _base(src)
    args += [
        "-c:v", video_encoder,
        "-b:v", str(video_bitrate),
        "-maxrate", str(int(video_bitrate * _MAXRATE_FACTOR)),
        "-bufsize", str(int(video_bitrate * _BUFSIZE_FACTOR)),
    ]
    if audio_bitrate:
        args += ["-c:a", "aac", "-b:a", str(audio_bitrate)]
    else:
        args.append("-an")
    return _finish(args, out)


def build_trim_args(
    src: Path,
    out: Path,
    start: float,
    end: float,
    precise: bool,
    video_encoder: str = "libx264",
) -> list[str]:
    if end <= start:
        raise ValueError("The end must come after the start")

    if precise:
        # Seeking after the input is frame-accurate but has to decode up to the
        # cut, so the streams must be re-encoded.
        args = _base(src) + ["-ss", str(start), "-to", str(end),
                             "-c:v", video_encoder, "-c:a", "aac"]
        return _finish(args, out)

    # Seeking before the input is instant, at the cost of landing on the
    # nearest keyframe rather than the exact moment asked for.
    #
    # A duration rather than an end time: after an input-side seek ffmpeg
    # measures -to from the seek point, so -ss 10 -to 20 yields twenty seconds
    # rather than ten. -t means the same thing whichever side it lands on.
    head = ["-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1", "-y"]
    args = head + ["-ss", str(start), "-t", str(end - start), "-i", str(src), "-c", "copy"]
    return _finish(args, out)


@dataclass
class EncodeResult:
    source: Path
    output: Path | None
    status: str
    source_bytes: int = 0
    output_bytes: int = 0
    detail: str = ""
    lossless: bool = False


def run_ffmpeg(
    args: list[str],
    duration: float | None = None,
    on_progress: Callable | None = None,
    runner: Callable | None = None,
    on_start: Callable[[int], None] | None = None,
) -> tuple[bool, str]:
    """Run ffmpeg, reporting progress as it goes. Returns (succeeded, message).

    `on_start` is handed the process id. ffmpeg outlives this program if the
    tool is quit, so something has to be able to find it again.
    """
    if runner is not None:
        return runner(args, duration, on_progress)

    reader = ProgressReader(duration)
    process = subprocess.Popen(
        ["ffmpeg", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    if on_start is not None:
        on_start(process.pid)

    assert process.stdout is not None
    for line in process.stdout:
        update = reader.feed(line)
        if update is not None and on_progress is not None:
            on_progress(update)

    _, errors = process.communicate()
    if process.returncode != 0:
        tail = (errors or "").strip().splitlines()
        return False, (tail[-1] if tail else f"ffmpeg exited with {process.returncode}")
    return True, ""
