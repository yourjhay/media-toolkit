import json
from pathlib import Path

from shared import settings


def test_nothing_remembered_yet_gives_the_fallback(tmp_path):
    store = tmp_path / "settings.json"

    assert settings.recall_path("video.dest", Path("/fallback"), store=store) == Path("/fallback")


def test_what_is_remembered_comes_back(tmp_path):
    store = tmp_path / "settings.json"

    settings.remember_path("video.dest", Path("/media/films"), store=store)

    assert settings.recall_path("video.dest", Path("/fallback"), store=store) == Path("/media/films")


def test_different_keys_do_not_collide(tmp_path):
    store = tmp_path / "settings.json"

    settings.remember_path("video.dest", Path("/movies"), store=store)
    settings.remember_path("image.dest", Path("/pictures"), store=store)

    assert settings.recall_path("video.dest", Path("/x"), store=store) == Path("/movies")
    assert settings.recall_path("image.dest", Path("/x"), store=store) == Path("/pictures")


def test_remembering_again_replaces_the_old_value(tmp_path):
    store = tmp_path / "settings.json"

    settings.remember_path("video.dest", Path("/first"), store=store)
    settings.remember_path("video.dest", Path("/second"), store=store)

    assert settings.recall_path("video.dest", Path("/x"), store=store) == Path("/second")


def test_the_file_is_created_along_with_its_folder(tmp_path):
    store = tmp_path / "nested" / "deeper" / "settings.json"

    settings.remember_path("video.dest", Path("/movies"), store=store)

    assert store.exists()


def test_a_corrupt_settings_file_does_not_break_anything(tmp_path):
    """A half-written file should cost a preference, not the whole session."""
    store = tmp_path / "settings.json"
    store.write_text("{not json at all")

    assert settings.recall_path("video.dest", Path("/fallback"), store=store) == Path("/fallback")


def test_a_corrupt_file_is_replaced_rather_than_appended_to(tmp_path):
    store = tmp_path / "settings.json"
    store.write_text("{not json at all")

    settings.remember_path("video.dest", Path("/movies"), store=store)

    assert json.loads(store.read_text())["video.dest"] == "/movies"


def test_a_settings_file_holding_the_wrong_shape_is_ignored(tmp_path):
    store = tmp_path / "settings.json"
    store.write_text('["a list, not an object"]')

    assert settings.recall_path("video.dest", Path("/fallback"), store=store) == Path("/fallback")


def test_a_remembered_path_that_no_longer_exists_is_still_offered(tmp_path):
    """It is a default in a prompt, not a promise; the user can edit it."""
    store = tmp_path / "settings.json"
    settings.remember_path("video.dest", Path("/gone/missing"), store=store)

    assert settings.recall_path("video.dest", Path("/fallback"), store=store) == Path("/gone/missing")


def test_saving_somewhere_unwritable_is_survivable(tmp_path):
    """Losing a convenience must never take a finished download with it."""
    blocked = tmp_path / "file-not-a-dir"
    blocked.write_text("x")

    settings.remember_path("video.dest", Path("/movies"), store=blocked / "settings.json")


def test_the_default_store_lives_under_the_user_config_directory():
    assert ".config" in str(settings.default_store())


def test_the_video_toolkit_keeps_its_two_destinations_apart():
    """Where videos are saved and where converted files land are different answers."""
    from video_toolkit.tui import DOWNLOAD_DEST, LOCAL_DEST

    assert DOWNLOAD_DEST != LOCAL_DEST
