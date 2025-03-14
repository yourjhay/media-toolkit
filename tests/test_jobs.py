from pathlib import Path

from image_toolkit.core import FAILED, OK, SHORT, SKIPPED, Result
from image_toolkit.jobs import run_batch


def _result(name, status, source_bytes=1000, output_bytes=400):
    return Result(Path(name), Path(f"out/{name}"), status, source_bytes, output_bytes)


def test_bytes_saved_counts_a_short_result_too():
    """A run that fell short of its target still shrank the file."""
    assert _result("a.jpg", SHORT, 1000, 700).bytes_saved == 300


def test_bytes_saved_ignores_skipped_and_failed():
    assert _result("a.jpg", SKIPPED, 1000, 900).bytes_saved == 0
    assert _result("a.jpg", FAILED, 1000, 0).bytes_saved == 0


def test_every_path_is_processed_in_order():
    seen = []

    def op(path):
        seen.append(path)
        return _result(path.name, OK)

    summary = run_batch([Path("a.jpg"), Path("b.jpg")], op)

    assert seen == [Path("a.jpg"), Path("b.jpg")]
    assert [r.source.name for r in summary.results] == ["a.jpg", "b.jpg"]


def test_one_failure_does_not_abort_the_rest():
    def op(path):
        if path.name == "bad.jpg":
            raise RuntimeError("encoder exploded")
        return _result(path.name, OK)

    summary = run_batch([Path("a.jpg"), Path("bad.jpg"), Path("c.jpg")], op)

    assert [r.status for r in summary.results] == [OK, FAILED, OK]
    assert "encoder exploded" in summary.results[1].detail


def test_summary_counts_each_status():
    statuses = [OK, OK, SKIPPED, FAILED, SHORT]
    paths = [Path(f"{i}.jpg") for i in range(len(statuses))]
    lookup = dict(zip(paths, statuses))

    summary = run_batch(paths, lambda p: _result(p.name, lookup[p]))

    assert summary.counts == {OK: 2, SKIPPED: 1, FAILED: 1, SHORT: 1}


def test_summary_totals_the_bytes_saved():
    paths = [Path("a.jpg"), Path("b.jpg")]

    summary = run_batch(paths, lambda p: _result(p.name, OK, 1000, 250))

    assert summary.bytes_saved == 1500


def test_progress_callback_fires_once_per_file():
    calls = []

    run_batch(
        [Path("a.jpg"), Path("b.jpg")],
        lambda p: _result(p.name, OK),
        on_progress=lambda result: calls.append(result.source.name),
    )

    assert calls == ["a.jpg", "b.jpg"]


def test_empty_input_yields_an_empty_summary():
    summary = run_batch([], lambda p: _result(p.name, OK))

    assert summary.results == []
    assert summary.bytes_saved == 0
    assert summary.counts == {}
