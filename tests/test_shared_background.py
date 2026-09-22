"""Work that carries on while you use the menu.

Threads, so the tests synchronise on events rather than sleeping: a test that
waits a fixed time either wastes it or fails on a slow machine.
"""

import threading

import pytest

from shared.background import DONE, FAILED, RUNNING, JobBoard


def test_a_job_is_running_the_moment_it_starts():
    board = JobBoard()
    release = threading.Event()

    job = board.start("encode", lambda on_progress: release.wait(2))
    try:
        assert job.status == RUNNING
        assert board.running_count() == 1
    finally:
        release.set()
        board.wait_all(timeout=2)


def test_a_finished_job_reports_its_result():
    board = JobBoard()

    board.start("encode", lambda on_progress: "the result")
    board.wait_all(timeout=2)

    job = board.jobs()[0]
    assert job.status == DONE
    assert job.result == "the result"


def test_a_job_that_raises_is_recorded_not_lost():
    """A background crash with nobody watching would otherwise vanish."""
    board = JobBoard()

    def boom(on_progress):
        raise RuntimeError("encoder exploded")

    board.start("encode", boom)
    board.wait_all(timeout=2)

    job = board.jobs()[0]
    assert job.status == FAILED
    assert "exploded" in job.detail


def test_progress_reaches_the_board():
    board = JobBoard()

    def work(on_progress):
        on_progress(42.0)
        return None

    board.start("encode", work)
    board.wait_all(timeout=2)

    assert board.jobs()[0].percent == pytest.approx(42.0)


def test_several_jobs_run_at_once():
    board = JobBoard()
    release = threading.Event()
    started = threading.Barrier(4, timeout=3)

    def work(on_progress):
        started.wait()
        release.wait(2)

    for i in range(3):
        board.start(f"job {i}", work)
    try:
        started.wait()  # all three reached the barrier, so all three are live
        assert board.running_count() == 3
    finally:
        release.set()
        board.wait_all(timeout=3)


def test_jobs_are_numbered_so_they_can_be_told_apart():
    board = JobBoard()

    first = board.start("a", lambda on_progress: None)
    second = board.start("b", lambda on_progress: None)
    board.wait_all(timeout=2)

    assert first.id != second.id


def test_a_finished_job_records_how_long_it_took():
    board = JobBoard()

    board.start("encode", lambda on_progress: None)
    board.wait_all(timeout=2)

    assert board.jobs()[0].elapsed is not None
    assert board.jobs()[0].elapsed >= 0


def test_a_running_job_reports_elapsed_time_as_it_goes():
    board = JobBoard()
    release = threading.Event()

    board.start("encode", lambda on_progress: release.wait(2))
    try:
        assert board.jobs()[0].elapsed >= 0
    finally:
        release.set()
        board.wait_all(timeout=2)


def test_finished_jobs_can_be_cleared_without_touching_running_ones():
    board = JobBoard()
    release = threading.Event()

    board.start("quick", lambda on_progress: None)
    board.wait_for(1, timeout=2)
    board.start("slow", lambda on_progress: release.wait(2))
    try:
        board.clear_finished()

        assert board.running_count() == 1
        assert [j.label for j in board.jobs()] == ["slow"]
    finally:
        release.set()
        board.wait_all(timeout=2)


def test_an_empty_board_is_quiet():
    board = JobBoard()

    assert board.jobs() == []
    assert board.running_count() == 0
    assert board.summary() == ""


def test_the_summary_counts_what_is_happening():
    board = JobBoard()

    board.start("a", lambda on_progress: None)
    board.wait_all(timeout=2)

    assert "1" in board.summary()


def test_a_non_numeric_progress_report_is_ignored_rather_than_stored():
    """ffmpeg reports an object, yt-dlp a different one. Only a number is a percent.

    Storing whatever arrives crashed the Jobs table with
    "unsupported format string passed to EncodeProgress.__format__".
    """
    board = JobBoard()

    class NotANumber:
        pass

    def work(on_progress):
        on_progress(NotANumber())
        return None

    board.start("encode", work)
    board.wait_all(timeout=2)

    assert board.jobs()[0].percent is None


def test_a_numeric_string_is_accepted_as_a_percent():
    board = JobBoard()

    board.start("encode", lambda on_progress: on_progress("55"))
    board.wait_all(timeout=2)

    assert board.jobs()[0].percent == pytest.approx(55.0)


def test_a_percent_is_kept_inside_nought_to_a_hundred():
    """Encoders overshoot their own reported duration; 103% reads as a bug."""
    board = JobBoard()

    board.start("a", lambda on_progress: on_progress(140))
    board.start("b", lambda on_progress: on_progress(-5))
    board.wait_all(timeout=2)

    assert [job.percent for job in board.jobs()] == [100.0, 0.0]
