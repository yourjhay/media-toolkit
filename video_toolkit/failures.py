"""Reading a download failure well enough to know what to suggest.

yt-dlp reports everything as one error string, so the difference between a
server having a bad moment and a video that simply is not there has to be read
back out of the text.
"""

from __future__ import annotations

# Nothing another attempt will fix: the video is gone, walled, or not ours to
# fetch. Checked first, since a dead end reached over a flaky connection is
# still a dead end.
_PERMANENT = (
    "video unavailable",
    "private video",
    "members only",
    "members-only",
    "removed by the uploader",
    "not made this video available",
    "not available in your country",
    "sign in to confirm",
    "unsupported url",
    "account associated with this video has been terminated",
    "video has been removed",
)

# Worth another go: throttling, a bad moment, a connection that dropped.
_TRANSIENT = (
    "403",
    "429",
    "500",
    "502",
    "503",
    "504",
    "timed out",
    "timeout",
    "connection reset",
    "connection refused",
    "connection aborted",
    "temporary failure",
    "nodename nor servname",
    "unable to download video data",
    "unable to extract",
    "fragment retries",
    "giving up",
)

_HINTS = (
    ("403", "YouTube often rejects the first attempt for no lasting reason. "
            "Another go usually works; if it keeps failing, update yt-dlp with "
            "`.venv/bin/pip install -U yt-dlp`."),
    ("429", "You are being rate limited. Wait a few minutes before trying again."),
    ("sign in to confirm", "That needs a signed-in session, which this tool does not "
                           "have, so trying again will not help."),
    ("private video", "That video is private, so trying again will not help."),
    ("members only", "That video is for channel members, so trying again will not help."),
    ("members-only", "That video is for channel members, so trying again will not help."),
    ("not available in your country", "That video is blocked in your region."),
    ("video unavailable", "That video is gone, or the link is wrong."),
    ("removed by the uploader", "That video is gone — the uploader removed it."),
    ("unsupported url", "yt-dlp has no extractor for that site."),
    ("timed out", "The connection timed out. Worth another go."),
    ("connection reset", "The connection dropped. Worth another go."),
)


def _haystack(detail: str | None) -> str:
    return (detail or "").lower()


def is_transient(detail: str | None) -> bool:
    """Whether another attempt stands a chance.

    An unrecognised failure counts as transient: offering a retry that turns
    out to be pointless costs one keypress, while withholding one that would
    have worked costs the download.
    """
    text = _haystack(detail)
    if not text.strip():
        return False
    if any(marker in text for marker in _PERMANENT):
        return False
    return True if any(marker in text for marker in _TRANSIENT) else True


def failure_hint(detail: str | None) -> str | None:
    """A sentence about what went wrong, when we recognise it."""
    text = _haystack(detail)
    for marker, hint in _HINTS:
        if marker in text:
            return hint
    return None
