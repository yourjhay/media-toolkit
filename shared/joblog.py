"""A record of jobs that outlive the session which started them.

ffmpeg and yt-dlp run as child processes. When the tool exits, its threads go
with it but those children do not: they are reparented and carry on. A job is
therefore genuinely still running after you quit, and the next session has no
way to know unless it was written down.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Record:
    pid: int
    label: str
    output: str | None
    command: str
    started_at: float
    # Where ffmpeg is writing its progress, and the length it is working
    # through, so a later session can work out how far along it is.
    progress: str | None = None
    duration: float | None = None


def default_store() -> Path:
    return Path.home() / ".config" / "rj-toolkit" / "jobs.json"


def _load(store: Path) -> list[dict]:
    try:
        data = json.loads(Path(store).read_text())
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save(store: Path, rows: list[dict]) -> None:
    try:
        store = Path(store)
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps(rows, indent=2))
    except Exception:
        pass  # losing the record must never take the conversion with it


def read(store: Path) -> list[Record]:
    records = []
    for row in _load(store):
        try:
            records.append(Record(**row))
        except TypeError:
            continue
    return records


def new_progress_path() -> Path:
    """A fresh file for ffmpeg to report progress into."""
    folder = default_store().parent / "progress"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        folder = Path(tempfile.gettempdir())
    return folder / f"{uuid.uuid4().hex}.txt"


def record(
    store: Path,
    pid: int,
    label: str,
    output: str | None,
    command: str,
    progress: str | None = None,
    duration: float | None = None,
) -> None:
    rows = _load(store)
    rows.append(asdict(Record(pid=pid, label=label, output=output, command=command,
                              started_at=time.time(), progress=progress,
                              duration=duration)))
    _save(store, rows)


def forget(store: Path, pid: int) -> None:
    """Drop a record, taking its progress file with it."""
    for row in _load(store):
        if row.get("pid") == pid and row.get("progress"):
            try:
                Path(row["progress"]).unlink(missing_ok=True)
            except OSError:
                pass
    _save(store, [row for row in _load(store) if row.get("pid") != pid])


def process_alive(pid: int, command: str) -> bool:
    """Whether that process is still running, and is still the one we started.

    A pid on its own proves nothing: the number is reused. The command line is
    checked too, so an unrelated process inheriting the number is not mistaken
    for a conversion still in flight.
    """
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError, PermissionError):
        return False

    try:
        running = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return False

    marker = (command or "").split()[0] if command else ""
    return bool(running) and marker in running


def _discard_progress(entry: Record) -> None:
    if not entry.progress:
        return
    try:
        Path(entry.progress).unlink(missing_ok=True)
    except OSError:
        pass


def live(store: Path, is_alive: Callable[[int, str], bool] | None = None) -> list[Record]:
    """The jobs still genuinely running, pruning the file of those that are not.

    A pruned job's progress file goes with it. Without that, every quit taken
    while something was converting would leave one behind for good.
    """
    check = is_alive or process_alive
    survivors, finished = [], []
    for entry in read(store):
        (survivors if check(entry.pid, entry.command) else finished).append(entry)

    for entry in finished:
        _discard_progress(entry)

    _save(store, [asdict(entry) for entry in survivors])
    return survivors


def forget_if_gone(
    store: Path,
    pid: int,
    is_alive: Callable[[int, str], bool] | None = None,
) -> bool:
    """Check on one recorded job, dropping the record once it has finished.

    The session that started it was killed, so its own cleanup never ran.
    Whoever notices the process is gone is the one who tidies up.
    """
    check = is_alive or process_alive
    command = next((entry.command for entry in read(store) if entry.pid == pid), "ffmpeg")
    if check(pid, command):
        return True
    forget(store, pid)
    return False
