"""The progress display.

Both bars are built from one helper so they cannot drift apart, which is also
what makes the columns checkable without running a terminal.
"""

from rich.progress import BarColumn, SpinnerColumn, TextColumn, TimeRemainingColumn

from video_toolkit.tui import progress_bar


def _column_types(progress):
    return [type(column) for column in progress.columns]


def test_a_spinner_leads_the_bar():
    """Something has to move while a long encode reports no percentage yet."""
    assert _column_types(progress_bar())[0] is SpinnerColumn


def test_the_description_follows_the_spinner():
    assert _column_types(progress_bar())[1] is TextColumn


def test_the_bar_percentage_and_remaining_time_are_all_there():
    types = _column_types(progress_bar())

    assert BarColumn in types
    assert TimeRemainingColumn in types
    assert types.count(TextColumn) >= 3, "description, percentage and rate"


def test_the_spinner_stops_when_the_task_does():
    """A spinner still turning after 'Done' says the tool has hung."""
    spinner = progress_bar().columns[0]

    # rich stores it as a Text, and the markup should already be parsed rather
    # than sitting in the output as literal square brackets.
    assert spinner.finished_text.plain.strip() != ""
    assert "[" not in spinner.finished_text.plain


def test_every_bar_in_the_toolkit_is_built_from_this_one_helper():
    """Two hand-rolled Progress blocks had already drifted once."""
    import pathlib

    import video_toolkit.tui

    source = pathlib.Path(video_toolkit.tui.__file__).read_text()

    assert source.count("Progress(") == 1, "Progress should only be constructed in progress_bar()"


def test_an_encoder_update_is_translated_into_a_plain_percent():
    """The job board wants a number; ffmpeg and yt-dlp both report objects."""
    from video_toolkit.tui import percent_reporter

    seen = []
    report = percent_reporter(seen.append)

    class Update:
        percent = 42.0

    report(Update())

    assert seen == [42.0]


def test_an_update_with_no_percent_yet_reports_nothing():
    from video_toolkit.tui import percent_reporter

    seen = []

    class Update:
        percent = None

    percent_reporter(seen.append)(Update())

    assert seen == []


# --- the jobs table ---------------------------------------------------------

def _fake_jobs():
    from shared.background import DONE, FAILED, RUNNING, Job

    running = Job(id=1, label="Converting to mov", status=RUNNING, percent=2.0)
    finished = Job(id=2, label="Download: a talk", status=DONE, percent=100.0)
    broken = Job(id=3, label="Compressing", status=FAILED, detail="boom")
    for job in (finished, broken):
        job.finished_at = job.started_at + 12.0
    return [running, finished, broken]


def test_the_table_has_a_row_for_every_job():
    from video_toolkit.tui import jobs_table

    assert jobs_table(_fake_jobs()).row_count == 3


def test_each_state_is_named():
    from video_toolkit.tui import jobs_view_text

    text = jobs_view_text(_fake_jobs(), width=90)

    assert "running" in text
    assert "done" in text
    assert "failed" in text


def test_progress_and_labels_reach_the_table():
    from video_toolkit.tui import jobs_view_text

    text = jobs_view_text(_fake_jobs(), width=90)

    assert "Converting to mov" in text
    assert "2%" in text


def test_a_job_with_no_progress_yet_shows_a_dash_not_a_zero():
    """Nought percent and "not reported yet" are different things."""
    from shared.background import Job
    from video_toolkit.tui import jobs_view_text

    text = jobs_view_text([Job(id=1, label="starting", percent=None)], width=90)

    assert "—" in text


def test_an_empty_board_makes_an_empty_table():
    from video_toolkit.tui import jobs_table

    assert jobs_table([]).row_count == 0


def test_the_view_says_how_to_leave_it():
    """A screen that refreshes itself needs to say what stops it."""
    from video_toolkit.tui import jobs_view_text

    assert "key" in jobs_view_text(_fake_jobs(), width=90).lower()
