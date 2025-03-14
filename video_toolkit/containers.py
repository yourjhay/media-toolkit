"""Which codecs a container will accept, and what that means for a conversion.

Changing a container is often free: if the streams inside are already legal in
the target format they can be copied across untouched, which takes a second
and loses nothing. Re-encoding is only necessary when they are not.
"""

from __future__ import annotations

from dataclasses import dataclass

COPY = "copy"
ENCODE = "encode"

CONTAINERS: dict[str, dict] = {
    "mp4": {
        "video": {"h264", "hevc", "av1", "mpeg4"},
        "audio": {"aac", "mp3", "alac"},
        "default_video": "h264",
        "default_audio": "aac",
    },
    "mov": {
        "video": {"h264", "hevc", "prores", "mpeg4"},
        "audio": {"aac", "alac", "pcm_s16le"},
        "default_video": "h264",
        "default_audio": "aac",
    },
    "mkv": {
        "video": {"h264", "hevc", "av1", "vp8", "vp9", "mpeg4", "theora"},
        "audio": {"aac", "mp3", "opus", "vorbis", "flac", "ac3", "alac", "pcm_s16le"},
        "default_video": "h264",
        "default_audio": "aac",
    },
    "webm": {
        "video": {"vp8", "vp9", "av1"},
        "audio": {"opus", "vorbis"},
        "default_video": "vp9",
        "default_audio": "opus",
    },
}

_SOFTWARE_ENCODERS = {
    "h264": "libx264",
    "hevc": "libx265",
    "vp9": "libvpx-vp9",
    "vp8": "libvpx",
    "av1": "libsvtav1",
    "aac": "aac",
    "opus": "libopus",
    "mp3": "libmp3lame",
    "vorbis": "libvorbis",
    "flac": "flac",
}

# Apple's hardware encoders, which are far faster but only exist for these.
_HARDWARE_ENCODERS = {"h264": "h264_videotoolbox", "hevc": "hevc_videotoolbox"}


# Codecs an Apple player is unlikely to play, even where the container accepts
# them. mp4 permits AV1 quite legally; QuickTime still will not open it.
_AWKWARD_ON_APPLE = {"av1", "vp9", "vp8"}
_APPLE_CONTAINERS = {"mp4", "mov"}


def playback_warning(video_codec: str | None, target_ext: str) -> str | None:
    """Why a legal conversion might still produce something that will not play.

    Only raised where the codec could otherwise be copied across: if it is
    being re-encoded anyway there is nothing to warn about.
    """
    target = (target_ext or "").lower().lstrip(".")
    if target not in _APPLE_CONTAINERS or video_codec not in _AWKWARD_ON_APPLE:
        return None
    if video_codec not in CONTAINERS[target]["video"]:
        return None  # already being re-encoded; no decision to make

    return (
        f"{video_codec} can be copied into {target} without re-encoding, but "
        f"Apple's own players do not open it. VLC and IINA will."
    )


@dataclass
class ConversionPlan:
    video: str | None
    audio: str | None
    video_encoder: str | None
    audio_encoder: str | None
    reason: str

    @property
    def video_lossless(self) -> bool:
        return self.video in (COPY, None)

    @property
    def lossless(self) -> bool:
        """True when nothing is re-encoded, so the conversion is a repackage."""
        return self.video in (COPY, None) and self.audio in (COPY, None)


def supported_targets() -> list[str]:
    return sorted(CONTAINERS)


def _encoder_for(codec: str, hardware: bool) -> str:
    if hardware and codec in _HARDWARE_ENCODERS:
        return _HARDWARE_ENCODERS[codec]
    return _SOFTWARE_ENCODERS.get(codec, codec)


def plan_conversion(
    video_codec: str | None,
    audio_codec: str | None,
    target_ext: str,
    hardware: bool = False,
    force_video_encode: bool = False,
) -> ConversionPlan:
    """What has to happen to put these streams into `target_ext`.

    `force_video_encode` re-encodes the video even when it could be copied,
    which is how a caller chooses a file that plays over one that is lossless.
    """
    target = target_ext.lower().lstrip(".")
    if target not in CONTAINERS:
        raise ValueError(
            f"Cannot write {target!r}; choose one of {', '.join(supported_targets())}"
        )
    spec = CONTAINERS[target]

    notes: list[str] = []

    if video_codec is None:
        video_action, video_encoder = None, None
    elif video_codec in spec["video"] and force_video_encode:
        wanted = spec["default_video"]
        video_action = ENCODE
        video_encoder = _encoder_for(wanted, hardware)
        notes.append(f"{video_codec} re-encoded to {wanted} so it will play")
    elif video_codec in spec["video"]:
        video_action, video_encoder = COPY, None
        notes.append(f"{video_codec} video carried across untouched")
    else:
        wanted = spec["default_video"]
        video_action = ENCODE
        video_encoder = _encoder_for(wanted, hardware)
        notes.append(f"{video_codec} is not allowed in {target}, re-encoding to {wanted}")

    if audio_codec is None:
        audio_action, audio_encoder = None, None
    elif audio_codec in spec["audio"]:
        audio_action, audio_encoder = COPY, None
        notes.append(f"{audio_codec} audio carried across untouched")
    else:
        wanted = spec["default_audio"]
        audio_action = ENCODE
        audio_encoder = _encoder_for(wanted, hardware)
        notes.append(f"{audio_codec} is not allowed in {target}, re-encoding to {wanted}")

    return ConversionPlan(
        video=video_action,
        audio=audio_action,
        video_encoder=video_encoder,
        audio_encoder=audio_encoder,
        reason="; ".join(notes) or "nothing to do",
    )
