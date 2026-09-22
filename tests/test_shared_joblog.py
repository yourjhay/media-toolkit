"""Remembering jobs across runs.

ffmpeg is a child process, not a thread. Quitting the tool leaves it running
and reparented to init, so a job genuinely survives the session that started
it — and the next session needs to know that rather than pretend otherwise.
"""

import json
import time

from shared import joblog


def test_nothing_recorded_yet_reads_as_empty(tmp_path):
    assert joblog.read(tmp_path / "jobs.json") == []


def test_a_recorded_job_comes_back(tmp_path):
    store = tmp_path / "jobs.json"

    joblog.record(store, pid=4321, label="Converting to mov", output="/out/a.mov",
                  command="ffmpeg -i a.mkv")

    [entry] = joblog.read(store)
    assert entry.pid == 4321
    assert entry.label == "Converting to mov"
    assert entry.output == "/out/a.mov"
    assert entry.started_at > 0


def test_several_jobs_are_kept_apart(tmp_path):
    store = tmp_path / "jobs.json"

    joblog.record(store, pid=1, label="a", output=None, command="ffmpeg a")
    joblog.record(store, pid=2, label="b", output=None, command="ffmpeg b")

    assert {e.pid for e in joblog.read(store)} == {1, 2}


def test_a_finished_job_is_forgotten(tmp_path):
    store = tmp_path / "jobs.json"
    joblog.record(store, pid=1, label="a", output=None, command="ffmpeg a")
    joblog.record(store, pid=2, label="b", output=None, command="ffmpeg b")

    joblog.forget(store, pid=1)

    assert [e.pid for e in joblog.read(store)] == [2]


def test_forgetting_something_unknown_is_harmless(tmp_path):
    store = tmp_path / "jobs.json"
    joblog.forget(store, pid=999)

    assert joblog.read(store) == []


def test_only_jobs_still_alive_are_reported(tmp_path):
    """A record outlives the process it describes whenever the tool is killed."""
    store = tmp_path / "jobs.json"
    joblog.record(store, pid=1, label="gone", output=None, command="ffmpeg a")
    joblog.record(store, pid=2, label="alive", output=None, command="ffmpeg b")

    alive = joblog.live(store, is_alive=lambda pid, command: pid == 2)

    assert [e.label for e in alive] == ["alive"]


def test_dead_jobs_are_pruned_from_the_file(tmp_path):
    store = tmp_path / "jobs.json"
    joblog.record(store, pid=1, label="gone", output=None, command="ffmpeg a")
    joblog.record(store, pid=2, label="alive", output=None, command="ffmpeg b")

    joblog.live(store, is_alive=lambda pid, command: pid == 2)

    assert [e.pid for e in joblog.read(store)] == [2]


def test_the_recorded_command_is_offered_for_checking(tmp_path):
    """A pid alone is not proof: the number gets reused by something else."""
    store = tmp_path / "jobs.json"
    joblog.record(store, pid=7, label="a", output=None, command="ffmpeg -i mine.mkv")

    seen = []
    joblog.live(store, is_alive=lambda pid, command: seen.append((pid, command)) or True)

    assert seen == [(7, "ffmpeg -i mine.mkv")]


def test_a_damaged_file_does_not_break_a_session(tmp_path):
    store = tmp_path / "jobs.json"
    store.write_text("{not json")

    assert joblog.read(store) == []


def test_a_damaged_file_is_replaced_rather_than_appended_to(tmp_path):
    store = tmp_path / "jobs.json"
    store.write_text("{not json")

    joblog.record(store, pid=1, label="a", output=None, command="ffmpeg a")

    assert json.loads(store.read_text())[0]["pid"] == 1


def test_an_unwritable_location_is_survivable(tmp_path):
    """Losing the record must not take the conversion with it."""
    blocked = tmp_path / "file"
    blocked.write_text("x")

    joblog.record(blocked / "jobs.json", pid=1, label="a", output=None, command="ffmpeg a")


def test_the_age_of_a_record_can_be_read_back(tmp_path):
    store = tmp_path / "jobs.json"
    joblog.record(store, pid=1, label="a", output=None, command="ffmpeg a")

    [entry] = joblog.read(store)
    assert 0 <= time.time() - entry.started_at < 60


def test_the_store_sits_beside_the_other_settings():
    assert joblog.default_store().parent.name == "rj-toolkit"


def test_a_record_is_dropped_as_soon_as_its_process_is_seen_gone(tmp_path):
    """The owning session was killed, so its own cleanup never ran. Whoever
    notices the process has finished is the one who has to tidy up."""
    store = tmp_path / "jobs.json"
    joblog.record(store, pid=1, label="a", output=None, command="ffmpeg a")

    joblog.forget_if_gone(store, pid=1, is_alive=lambda pid, command: False)

    assert joblog.read(store) == []


def test_a_record_for_something_still_running_is_kept(tmp_path):
    store = tmp_path / "jobs.json"
    joblog.record(store, pid=1, label="a", output=None, command="ffmpeg a")

    alive = joblog.forget_if_gone(store, pid=1, is_alive=lambda pid, command: True)

    assert alive is True
    assert len(joblog.read(store)) == 1


def test_asking_about_an_unknown_pid_reports_it_gone(tmp_path):
    store = tmp_path / "jobs.json"

    assert joblog.forget_if_gone(store, pid=999, is_alive=lambda pid, command: False) is False
