"""Telling a hiccup apart from a dead end.

Offering to retry a private video wastes someone's time; not offering to retry
a 403 wastes it more, since that one usually works on the second go.
"""

import pytest

from video_toolkit.failures import failure_hint, is_transient

TRANSIENT = [
    "DownloadError: ERROR: unable to download video data: HTTP Error 403: Forbidden",
    "DownloadError: HTTP Error 429: Too Many Requests",
    "DownloadError: HTTP Error 500: Internal Server Error",
    "DownloadError: HTTP Error 503: Service Unavailable",
    "TimeoutError: The read operation timed out",
    "DownloadError: [Errno 54] Connection reset by peer",
    "URLError: <urlopen error [Errno 8] nodename nor servname provided>",
    "DownloadError: Unable to extract player response",
    "DownloadError: giving up after 3 fragment retries",
]

PERMANENT = [
    "DownloadError: ERROR: Video unavailable",
    "DownloadError: Private video. Sign in if you've been granted access",
    "DownloadError: This video is available to members only",
    "DownloadError: The uploader has not made this video available in your country",
    "DownloadError: This video has been removed by the uploader",
    "DownloadError: Sign in to confirm you're not a bot",
    "DownloadError: Sign in to confirm your age",
    "UnsupportedError: Unsupported URL: https://example.com/whatever",
]


@pytest.mark.parametrize("detail", TRANSIENT)
def test_a_hiccup_is_worth_another_go(detail):
    assert is_transient(detail) is True


@pytest.mark.parametrize("detail", PERMANENT)
def test_a_dead_end_is_not(detail):
    assert is_transient(detail) is False


def test_an_unrecognised_failure_is_worth_one_more_try():
    """Erring towards offering costs a keypress; erring against costs the download."""
    assert is_transient("SomethingNobodyHasSeenBefore: 42") is True


def test_nothing_at_all_is_not_treated_as_a_hiccup():
    assert is_transient("") is False
    assert is_transient(None) is False


def test_a_forbidden_response_explains_itself():
    hint = failure_hint("HTTP Error 403: Forbidden")

    assert hint is not None
    assert "yt-dlp" in hint


def test_rate_limiting_advises_waiting_rather_than_hammering():
    hint = failure_hint("HTTP Error 429: Too Many Requests")

    assert "wait" in hint.lower()


def test_a_login_wall_says_retrying_will_not_help():
    hint = failure_hint("Sign in to confirm you're not a bot")

    assert "sign" in hint.lower() or "logged in" in hint.lower()
    assert "retry" in hint.lower() or "again" in hint.lower()


def test_a_missing_video_says_so_plainly():
    assert "gone" in failure_hint("Video unavailable").lower()


def test_an_unrecognised_failure_offers_no_advice_rather_than_guessing():
    assert failure_hint("SomethingNobodyHasSeenBefore: 42") is None


def test_the_classification_is_not_confused_by_case():
    assert is_transient("http error 403: forbidden") is True
    assert is_transient("VIDEO UNAVAILABLE") is False


def test_a_dead_end_wins_over_a_hiccup_when_both_appear():
    """A private video reached over a flaky link is still a private video."""
    assert is_transient("HTTP Error 403: Forbidden — Private video") is False
