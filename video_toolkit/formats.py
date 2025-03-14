"""Choosing what to ask yt-dlp for, and describing what it offers back.

Pure decisions about format strings and table rows, so the awkward parts —
what is downloadable without a merger, how to label a stream that carries only
half a video — are settled in tests rather than against a live site.
"""

from __future__ import annotations

from shared.format import human_bytes

MP3 = "mp3"
M4A = "m4a"
AUDIO_CODECS = (MP3, M4A)

VIDEO = "video"
AUDIO = "audio"
MODES = (VIDEO, AUDIO)

# Most sites serve anything above this as separate video and audio streams,
# which have to be muxed back together. Without ffmpeg only the pre-muxed
# formats can be taken, and those stop around here.
NO_FFMPEG_CEILING = 720


def format_selector(mode: str, ffmpeg: bool, max_height: int | None = None) -> str:
    """The format expression yt-dlp should be given.

    With ffmpeg the best video and best audio are requested separately and
    merged. Without it only already-combined formats are asked for: requesting
    a merge with no merger available produces a download that cannot finish.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")

    if mode == AUDIO:
        # m4a first so the file is usable as-is when there is nothing to convert with.
        return "bestaudio/best" if ffmpeg else "bestaudio[ext=m4a]/bestaudio/best"

    limit = f"[height<=?{max_height}]" if max_height else ""
    if ffmpeg:
        return f"bestvideo{limit}+bestaudio/best{limit}/best"
    return f"best{limit}/best"


def quality_warning(ffmpeg: bool) -> str | None:
    """What to tell the user when the merger is missing, and how to fix it."""
    if ffmpeg:
        return None
    return (
        f"ffmpeg is not installed, so only already-combined streams can be "
        f"downloaded — usually up to {NO_FFMPEG_CEILING}p. "
        f"Run  brew install ffmpeg  to lift that."
    )


def _resolution(fmt: dict) -> str:
    height = fmt.get("height")
    return f"{height}p" if height else "—"


def _kind(fmt: dict) -> str:
    has_video = fmt.get("vcodec") not in (None, "none")
    has_audio = fmt.get("acodec") not in (None, "none")
    if has_video and has_audio:
        return "video + audio"
    if has_video:
        return "video only"
    if has_audio:
        return "audio only"
    return "—"


def _size(fmt: dict) -> str:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    return human_bytes(size) if size else "—"


def describe_format(fmt: dict) -> dict[str, str]:
    """One format as a row a person can read."""
    fps = fmt.get("fps")
    return {
        "id": str(fmt.get("format_id", "—")),
        "ext": str(fmt.get("ext", "—")),
        "resolution": _resolution(fmt),
        "fps": f"{int(fps)}" if fps else "—",
        "size": _size(fmt),
        "kind": _kind(fmt),
    }


def readable_formats(info: dict) -> list[dict[str, str]]:
    """Every format on offer, best first."""
    formats = info.get("formats") or []
    ordered = sorted(
        formats,
        key=lambda f: (
            f.get("height") or 0,
            f.get("tbr") or 0,
            f.get("filesize") or f.get("filesize_approx") or 0,
        ),
        reverse=True,
    )
    return [describe_format(fmt) for fmt in ordered]


def audio_postprocessors(
    convert_to: str | None,
    quality: str = "192",
    tags: bool = True,
    cover: bool = True,
) -> list[dict]:
    """The ffmpeg steps applied to a downloaded audio stream.

    Sites serve their best audio as opus in a webm container: playable, but not
    what most people expect an audio file to be, so converting is offered.

    Tags and cover art are written by default. Without them a player shows an
    unknown artist and a blank square, which is what an untagged file looks
    like even though the information was there all along. yt-dlp takes the
    artist from the uploader and the genre from the video's own categories.

    Order matters: the audio has to exist before anything can be written into
    it, and the tags before the picture.
    """
    if convert_to is not None and convert_to not in AUDIO_CODECS:
        raise ValueError(f"codec must be one of {AUDIO_CODECS}, got {convert_to!r}")

    steps: list[dict] = []
    if convert_to is not None:
        steps.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": convert_to,
            "preferredquality": quality,
        })
    if tags:
        steps.append({"key": "FFmpegMetadata", "add_metadata": True})
    if cover:
        steps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    return steps
