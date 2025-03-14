"""Working out what bitrate hits a target file size."""

from __future__ import annotations

from shared.format import human_bytes

# Aim a little under. Container headers, indexes and per-frame overhead all
# cost bytes that the bitrate figure does not account for, so encoding exactly
# to target reliably lands just over it.
SAFETY_MARGIN = 0.97

# Below this a video is not worth having; better to say so than to produce it.
MIN_VIDEO_BITRATE = 100_000


def target_bitrate(
    duration: float,
    target_bytes: int,
    audio_bitrate: int = 128_000,
) -> int:
    """Video bitrate, in bits per second, that fits `target_bytes`.

    File size is bitrate times duration, so the arithmetic is simple; what
    matters is the parts people forget. The audio takes its share first, and
    the container takes a little more.
    """
    if duration <= 0:
        raise ValueError("The clip's length is unknown, so no bitrate can be worked out")
    if target_bytes <= 0:
        raise ValueError("The target size must be greater than zero")

    budget_bits = target_bytes * 8 * SAFETY_MARGIN
    audio_bits = audio_bitrate * duration

    if audio_bits >= budget_bits:
        raise ValueError(
            f"The audio alone needs about {human_bytes(audio_bits / 8)} at "
            f"{audio_bitrate // 1000} kbps, which already exceeds a "
            f"{human_bytes(target_bytes)} target"
        )

    video_bitrate = int((budget_bits - audio_bits) / duration)

    if video_bitrate < MIN_VIDEO_BITRATE:
        raise ValueError(
            f"That target leaves only {video_bitrate // 1000} kbps for video, "
            f"below the {MIN_VIDEO_BITRATE // 1000} kbps worth watching. "
            f"Try a larger size, or trim the clip first."
        )

    return video_bitrate
