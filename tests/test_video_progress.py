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
