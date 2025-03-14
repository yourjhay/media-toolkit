"""Fetching a video with yt-dlp.

yt-dlp is injectable so the logic here — what to ask for, where files land,
how progress and failures are reported — can be tested without a network or a
live site. The library itself is not re-tested; only our use of it.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .formats import VIDEO, audio_postprocessors, format_selector

OK = "ok"
FAILED = "failed"


@dataclass
class ProgressUpdate:
    downloaded: int = 0
    total: int | None = None
    percent: float | None = None
    speed: float | None = None
    eta: int | None = None
    finished: bool = False
    filename: str | None = None


@dataclass
class VideoInfo:
    url: str
    title: str | None = None
    uploader: str | None = None
    duration: float | None = None
    formats: list[dict] | None = None
    entries: int = 0
    error: str | None = None

    @property
    def is_playlist(self) -> bool:
        return self.entries > 1


@dataclass
class DownloadResult:
    url: str
    status: str
    title: str | None = None
    path: Path | None = None
    size_bytes: int = 0
    detail: str = ""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def read_progress(hook: dict) -> ProgressUpdate:
    """One of yt-dlp's progress dicts, in a shape worth rendering.

    The exact total is often unknown mid-download, so an estimate is used when
    there is one and no percentage is claimed when there is neither.
    """
    total = hook.get("total_bytes") or hook.get("total_bytes_estimate")
    downloaded = hook.get("downloaded_bytes") or 0
    percent = (downloaded / total * 100) if total else None
    return ProgressUpdate(
        downloaded=downloaded,
        total=total or None,
        percent=percent,
        speed=hook.get("speed"),
        eta=hook.get("eta"),
        finished=hook.get("status") == "finished",
        filename=hook.get("filename"),
    )


def _youtube_dl():
    from yt_dlp import YoutubeDL

    return YoutubeDL


def _quiet_options() -> dict:
    return {"quiet": True, "no_warnings": True, "noprogress": True, "consoletitle": False}


def probe(url: str, ydl_factory: Callable | None = None) -> VideoInfo:
    """Look up what a URL offers, without downloading anything."""
    factory = ydl_factory or _youtube_dl()
    options = {**_quiet_options(), "skip_download": True, "outtmpl": "%(title)s.%(ext)s"}

    try:
        with factory(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        return VideoInfo(url=url, error=f"{type(exc).__name__}: {exc}")

    entries = info.get("entries")
    if entries is not None:
        entries = list(entries)
        first = entries[0] if entries else {}
        return VideoInfo(
            url=url,
            title=info.get("title") or first.get("title"),
            uploader=info.get("uploader") or first.get("uploader"),
            duration=first.get("duration"),
            formats=first.get("formats"),
            entries=len(entries),
        )

    return VideoInfo(
        url=url,
        title=info.get("title"),
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        formats=info.get("formats"),
        entries=1,
    )


def resolve_output(
    info: dict,
    written: list[str],
    fallback: str,
    convert_to: str | None,
) -> Path:
    """Where the file actually ended up.

    Conversion replaces the downloaded file, so the name reported by the
    download hook may already be gone by the time we look. yt-dlp records the
    final path when it has one; otherwise the extension is swapped to match
    what was asked for.
    """
    requested = info.get("requested_downloads") or []
    for entry in reversed(requested):
        if entry.get("filepath"):
            return Path(entry["filepath"])

    last = Path(written[-1]) if written else Path(fallback)
    if convert_to and last.suffix.lstrip(".") != convert_to:
        return last.with_suffix(f".{convert_to}")
    return last


def download(
    url: str,
    dest_dir: Path,
    mode: str = VIDEO,
    max_height: int | None = None,
    ffmpeg: bool | None = None,
    convert_to: str | None = None,
    keep_original: bool = False,
    tags: bool = True,
    cover: bool = True,
    on_progress: Callable[[ProgressUpdate], None] | None = None,
    ydl_factory: Callable | None = None,
) -> DownloadResult:
    """Fetch one URL into `dest_dir`, reporting progress as it goes."""
    dest_dir = Path(dest_dir)
    factory = ydl_factory or _youtube_dl()
    if ffmpeg is None:
        ffmpeg = ffmpeg_available()

    written: list[str] = []

    def hook(raw: dict) -> None:
        update = read_progress(raw)
        if update.finished and update.filename:
            written.append(update.filename)
        if on_progress is not None:
            on_progress(update)

    options = {
        **_quiet_options(),
        "format": format_selector(mode=mode, ffmpeg=ffmpeg, max_height=max_height),
        "outtmpl": str(dest_dir / "%(title)s.%(ext)s"),
        "progress_hooks": [hook],
        "ignoreerrors": False,
        # yt-dlp's command line retries by default; the library does not, so a
        # single 403 from a server having a bad moment gave up immediately.
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "socket_timeout": 30,
        "postprocessors": audio_postprocessors(convert_to, tags=tags, cover=cover),
        # EmbedThumbnail has nothing to work with unless the image is fetched.
        "writethumbnail": bool(cover),
        # Whether the downloaded stream survives the conversion that replaces it.
        "keepvideo": keep_original,
    }

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with factory(options) as ydl:
            info = ydl.extract_info(url, download=True)
            fallback = ydl.prepare_filename(info)
    except Exception as exc:
        return DownloadResult(url=url, status=FAILED, detail=f"{type(exc).__name__}: {exc}")

    path = resolve_output(info, written, fallback, convert_to)
    if not path.exists():
        return DownloadResult(
            url=url, status=FAILED, title=info.get("title"),
            detail=f"yt-dlp reported success but {path.name} is not there",
        )

    return DownloadResult(
        url=url, status=OK, title=info.get("title"),
        path=path, size_bytes=path.stat().st_size,
    )
