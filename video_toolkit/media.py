"""Looking at a local media file, and following ffmpeg's progress."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class MediaInfo:
    path: Path
    size_bytes: int = 0
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    audio_bitrate: int | None = None
    video_bitrate: int | None = None
    error: str | None = None

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}×{self.height}"
        return "—"


def _ffprobe(args: list[str]) -> str:
    return subprocess.run(
        ["ffprobe", *args], capture_output=True, text=True, check=True, timeout=120
    ).stdout


def _number(value, cast=float):
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def probe_media(path: Path, runner: Callable[[list[str]], str] | None = None) -> MediaInfo:
    """What ffprobe can tell us about a local file."""
    path = Path(path)
    info = MediaInfo(path=path)

    if not path.is_file():
        info.error = f"No such file: {path}"
        return info

    info.size_bytes = path.stat().st_size
    run = runner or _ffprobe

    try:
        raw = run([
            "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ])
        data = json.loads(raw)
    except Exception as exc:
        info.error = f"{type(exc).__name__}: {exc}"
        return info

    info.duration = _number((data.get("format") or {}).get("duration"))

    for stream in data.get("streams") or []:
        kind = stream.get("codec_type")
        if kind == "video" and info.video_codec is None:
            info.video_codec = stream.get("codec_name")
            info.width = _number(stream.get("width"), int)
            info.height = _number(stream.get("height"), int)
            info.video_bitrate = _number(stream.get("bit_rate"), int)
        elif kind == "audio" and info.audio_codec is None:
            info.audio_codec = stream.get("codec_name")
            info.audio_bitrate = _number(stream.get("bit_rate"), int)

    if info.video_bitrate is None and info.video_codec:
        # Plenty of files report only an overall rate. The video is nearly all
        # of it, so the container figure less the audio is a fair stand-in.
        overall = _number((data.get("format") or {}).get("bit_rate"), int)
        if overall:
            info.video_bitrate = max(1, overall - (info.audio_bitrate or 0))

    return info


@dataclass
class EncodeProgress:
    seconds: float = 0.0
    percent: float | None = None
    speed: float | None = None
    finished: bool = False


class ProgressReader:
    """Turns ffmpeg's `-progress` output into something worth drawing.

    ffmpeg emits a run of `key=value` lines and then a `progress=` line that
    closes the block, so a block is only reported once it is complete.
    """

    def __init__(self, duration: float | None):
        self.duration = duration
        self._fields: dict[str, str] = {}

    def feed(self, line: str) -> EncodeProgress | None:
        line = line.strip()
        if "=" not in line:
            return None

        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()

        if key != "progress":
            self._fields[key] = value
            return None

        micros = _number(self._fields.get("out_time_us"))
        seconds = (micros / 1_000_000) if micros is not None else 0.0

        percent = None
        if self.duration:
            # Encoders overrun the reported duration by a frame or two.
            percent = min(100.0, seconds / self.duration * 100)

        speed = _number((self._fields.get("speed") or "").rstrip("x"))

        finished = value == "end"
        if finished:
            percent = 100.0 if self.duration else None

        self._fields.clear()
        return EncodeProgress(seconds=seconds, percent=percent, speed=speed, finished=finished)


def read_progress_file(path, duration: float | None) -> EncodeProgress | None:
    """The latest complete block from an ffmpeg `-progress` file.

    Written to a file rather than a pipe so that a job outliving the session
    which started it can still be followed. The file is read while ffmpeg is
    writing it, so a trailing partial block is expected and skipped.
    """
    try:
        text = Path(path).read_text()
    except OSError:
        return None
    if not text.strip():
        return None

    reader = ProgressReader(duration)
    latest = None
    for line in text.splitlines():
        update = reader.feed(line)
        if update is not None:
            latest = update
    return latest
