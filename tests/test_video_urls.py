import pytest

from video_toolkit.urls import clean_url


def test_surrounding_whitespace_is_stripped():
    assert clean_url("  https://example.com/watch?v=1  ") == "https://example.com/watch?v=1"


@pytest.mark.parametrize("quoted", ["'https://example.com/a'", '"https://example.com/a"'])
def test_quoted_urls_are_unwrapped(quoted):
    """Copying a link out of a chat app often brings the quotes along."""
    assert clean_url(quoted) == "https://example.com/a"


def test_a_bare_host_gets_a_scheme():
    assert clean_url("example.com/watch?v=1") == "https://example.com/watch?v=1"


def test_http_is_left_as_it_was_given():
    assert clean_url("http://example.com/a") == "http://example.com/a"


def test_empty_input_is_rejected():
    for blank in ("", "   ", "''"):
        with pytest.raises(ValueError):
            clean_url(blank)


def test_something_that_is_not_a_link_is_rejected():
    with pytest.raises(ValueError):
        clean_url("just some words")


def test_a_local_file_path_is_rejected_rather_than_guessed_at():
    with pytest.raises(ValueError):
        clean_url("/Users/rj/Downloads/video.mp4")
