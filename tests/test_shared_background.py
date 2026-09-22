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


# --- jobs that outlived the session which started them -----------------------

def test_a_job_from_a_previous_run_can_be_adopted():
    """ffmpeg survives the tool exiting, so the next run should show it."""
    board = JobBoard()

    job = board.adopt("Converting to mov", pid=4321, output="/out/a.mov", age=90.0)

    assert job.status == RUNNING
    assert job.pid == 4321
    assert job.elapsed >= 90.0
    assert board.running_count() == 1


def test_an_adopted_job_is_marked_finished_once_its_process_goes():
    board = JobBoard()
    board.adopt("Converting", pid=4321, output=None, age=1.0)

    board.refresh(is_alive=lambda pid: False)

    assert board.jobs()[0].status == DONE


def test_an_adopted_job_still_running_is_left_alone():
    board = JobBoard()
    board.adopt("Converting", pid=4321, output=None, age=1.0)

    board.refresh(is_alive=lambda pid: True)

    assert board.jobs()[0].status == RUNNING


def test_refreshing_does_not_disturb_jobs_this_session_started():
    """Those have a thread reporting for them; their state is already right."""
    board = JobBoard()
    board.start("mine", lambda on_progress: None)
    board.wait_all(timeout=2)

    board.refresh(is_alive=lambda pid: False)

    assert board.jobs()[0].status == DONE


def test_an_adopted_job_reports_no_progress_rather_than_a_made_up_figure():
    """Its progress was on a pipe this process no longer holds."""
    board = JobBoard()

    job = board.adopt("Converting", pid=1, output=None, age=1.0)

    assert job.percent is None


def test_the_pids_of_running_jobs_can_be_listed_for_stopping():
    board = JobBoard()
    board.adopt("a", pid=11, output=None, age=1.0)
    board.adopt("b", pid=22, output=None, age=1.0)

    assert set(board.running_pids()) == {11, 22}


def test_a_job_with_no_pid_is_not_offered_for_stopping():
    board = JobBoard()
    release = threading.Event()
    board.start("threaded", lambda on_progress: release.wait(2))
    try:
        assert board.running_pids() == []
    finally:
        release.set()
        board.wait_all(timeout=2)
