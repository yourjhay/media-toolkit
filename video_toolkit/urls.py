"""Making sense of a link as people actually paste one."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_QUOTE_PAIRS = (("'", "'"), ('"', '"'))
_LOOKS_LIKE_HOST = re.compile(r"^[\w.-]+\.[a-z]{2,}(/|$|\?)", re.I)

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}

# Parameters that change a single video into something else, or that only
# exist to track where the link was shared.
_STRIP_WITH_VIDEO = {"list", "start_radio", "index", "pp", "si"}
_ALWAYS_STRIP = {"si"}


def _tidy_youtube(url: str) -> str:
    """Reduce a YouTube link to the thing it actually points at.

    A watch link carrying `list=RD…` is a radio mix: an endless, generated
    playlist. Downloading it means downloading forever. When the link names a
    specific video, that video is what was meant.
    """
    parts = urlparse(url)
    if parts.netloc.lower() not in _YOUTUBE_HOSTS:
        return url

    query = parse_qsl(parts.query, keep_blank_values=True)
    names = {key for key, _ in query}
    has_video = "v" in names or parts.netloc.lower() == "youtu.be"

    drop = _STRIP_WITH_VIDEO if has_video else _ALWAYS_STRIP
    kept = [(key, value) for key, value in query if key not in drop]

    return urlunparse(parts._replace(query=urlencode(kept)))


def clean_url(raw: str) -> str:
    """Turn a pasted link into one yt-dlp can use.

    Copied links arrive wrapped in quotes or padded with spaces, and people
    often paste a bare host with no scheme. Anything that is plainly not a
    link is rejected here rather than handed to yt-dlp to puzzle over.
    """
    text = raw.strip()
    for opening, closing in _QUOTE_PAIRS:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            text = text[1:-1].strip()
            break

    if not text:
        raise ValueError("No link given")

    if text.startswith(("http://", "https://")):
        return _tidy_youtube(text)

    if text.startswith("/") or text.startswith("~"):
        raise ValueError("That looks like a file on this machine, not a link")

    if _LOOKS_LIKE_HOST.match(text):
        return _tidy_youtube(f"https://{text}")

    raise ValueError(f"That does not look like a link: {text[:60]}")
