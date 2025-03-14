"""Making sense of a link as people actually paste one."""

from __future__ import annotations

import re

_QUOTE_PAIRS = (("'", "'"), ('"', '"'))
_LOOKS_LIKE_HOST = re.compile(r"^[\w.-]+\.[a-z]{2,}(/|$|\?)", re.I)


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
        return text

    if text.startswith("/") or text.startswith("~"):
        raise ValueError("That looks like a file on this machine, not a link")

    if _LOOKS_LIKE_HOST.match(text):
        return f"https://{text}"

    raise ValueError(f"That does not look like a link: {text[:60]}")
