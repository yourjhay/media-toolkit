"""Progress that survives the session which started it.

ffmpeg reported down a pipe held by the tool. When the tool was killed the
pipe died with it, so a job adopted by the next run could show elapsed time
but never a percentage. A file can be read by whoever is around to read it.
"""

import pytest

from video_toolkit.media import read_progress_file

BLOCK = """frame=120
fps=30.0
out_time_us=4000000
speed=2.11x
progress=continue
"""


def test_the_latest_position_is_read_back(tmp_path):
    path = tmp_path / "prog.txt"
    path.write_text(BLOCK)

    update = read_progress_file(path, duration=10.0)

    assert update.seconds == pytest.approx(4.0)
    assert update.percent == pytest.approx(40.0)


def test_the_most_recent_block_wins(tmp_path):
    """ffmpeg appends; the file holds every block it has ever written."""
    path = tmp_path / "prog.txt"
    path.write_text(BLOCK + BLOCK.replace("out_time_us=4000000", "out_time_us=9000000"))

    assert read_progress_file(path, duration=10.0).percent == pytest.approx(90.0)


def test_a_finished_encode_is_recognised(tmp_path):
    path = tmp_path / "prog.txt"
    path.write_text(BLOCK + "out_time_us=10000000\nprogress=end\n")

    update = read_progress_file(path, duration=10.0)

    assert update.finished is True
    assert update.percent == 100.0


def test_a_half_written_block_is_ignored_until_it_is_complete(tmp_path):
    """The file is read while it is being written, so the tail is often partial."""
    path = tmp_path / "prog.txt"
    path.write_text(BLOCK + "frame=200\nout_time_us=8000000\n")

    assert read_progress_file(path, duration=10.0).percent == pytest.approx(40.0)


def test_a_file_that_does_not_exist_yet_reports_nothing(tmp_path):
    assert read_progress_file(tmp_path / "missing.txt", duration=10.0) is None


def test_an_empty_file_reports_nothing(tmp_path):
    path = tmp_path / "prog.txt"
    path.write_text("")

    assert read_progress_file(path, duration=10.0) is None


def test_without_a_duration_there_is_no_percentage(tmp_path):
    path = tmp_path / "prog.txt"
    path.write_text(BLOCK)

    update = read_progress_file(path, duration=None)

    assert update.percent is None
    assert update.seconds == pytest.approx(4.0)


def test_the_speed_is_carried_through(tmp_path):
    path = tmp_path / "prog.txt"
    path.write_text(BLOCK)

    assert read_progress_file(path, duration=10.0).speed == pytest.approx(2.11)
