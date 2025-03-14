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


def test_a_radio_mix_link_is_reduced_to_the_video_it_names():
    """`list=RD…` turns a watch link into an endless auto-generated mix."""
    messy = "https://www.youtube.com/watch?v=9cwf3BGhqFA&list=RD9cwf3BGhqFA&start_radio=1"

    assert clean_url(messy) == "https://www.youtube.com/watch?v=9cwf3BGhqFA"


def test_a_share_token_is_dropped():
    cleaned = clean_url("https://youtu.be/BrnDlRmW5hs?si=D5tXmw9NR40_TTdM")

    assert "si=" not in cleaned
    assert "BrnDlRmW5hs" in cleaned


def test_a_position_in_a_playlist_is_dropped_along_with_the_playlist():
    cleaned = clean_url("https://www.youtube.com/watch?v=abc123&list=PL123&index=7")

    assert cleaned == "https://www.youtube.com/watch?v=abc123"


def test_a_genuine_playlist_link_is_left_alone():
    """No video id means the playlist really is what was asked for."""
    link = "https://www.youtube.com/playlist?list=PLabcdef"

    assert clean_url(link) == link


def test_a_start_time_is_kept():
    cleaned = clean_url("https://www.youtube.com/watch?v=abc123&t=42")

    assert "t=42" in cleaned


def test_links_from_other_sites_keep_their_query_intact():
    link = "https://example.com/video?id=7&list=keepme"

    assert clean_url(link) == link
