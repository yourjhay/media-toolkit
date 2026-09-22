"""Running a slow job while the menu stays usable.

Each job gets a thread. The work itself is a subprocess — ffmpeg, yt-dlp — so
the interpreter lock is not in the way; the thread only waits on it.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

RUNNING = "running"
DONE = "done"
FAILED = "failed"


@dataclass
class Job:
    id: int
    label: str
    status: str = RUNNING
    percent: float | None = None
    detail: str = ""
    result: Any = None
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    # Set only for a job adopted from an earlier run, where the work is a
    # process we did not start and have no pipe to.
    pid: int | None = None

    @property
    def elapsed(self) -> float:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return end - self.started_at

    @property
    def is_running(self) -> bool:
        return self.status == RUNNING


class JobBoard:
    """Jobs started from the menu, and what became of them."""

    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self._threads: dict[int, threading.Thread] = {}
        self._events: dict[int, threading.Event] = {}
        self._lock = threading.Lock()
        self._next_id = 1

    def start(self, label: str, work: Callable[[Callable[[float], None]], Any]) -> Job:
        """Run `work` on a thread. It is handed a callback to report percent."""
        with self._lock:
            job = Job(id=self._next_id, label=label)
            self._next_id += 1
            self._jobs.append(job)
            done = threading.Event()
            self._events[job.id] = done

        def on_progress(percent: Any) -> None:
            # Callers report all sorts of things. Only a number is a percent,
            # and anything else would break the display that renders it.
            try:
                value = float(percent)
            except (TypeError, ValueError):
                return
            with self._lock:
                job.percent = max(0.0, min(100.0, value))

        def run() -> None:
            try:
                value = work(on_progress)
            except Exception as exc:
                with self._lock:
                    job.status = FAILED
                    job.detail = f"{type(exc).__name__}: {exc}"
            else:
                with self._lock:
                    job.status = DONE
                    job.result = value
            finally:
                with self._lock:
                    job.finished_at = time.monotonic()
                done.set()

        thread = threading.Thread(target=run, name=f"job-{job.id}", daemon=True)
        with self._lock:
            self._threads[job.id] = thread
        thread.start()
        return job

    def adopt(self, label: str, pid: int, output: str | None, age: float) -> Job:
        """Take on a job left running by a previous session.

        There is no thread and no progress pipe — only a process id — so its
        state is worked out by asking whether that process is still there.
        """
        with self._lock:
            job = Job(
                id=self._next_id,
                label=label,
                pid=pid,
                started_at=time.monotonic() - age,
            )
            job.detail = f"started before this session; writing to {output}" if output else ""
            self._next_id += 1
            self._jobs.append(job)
        return job

    def refresh(self, is_alive: Callable[[int], bool]) -> None:
        """Update adopted jobs by checking whether their process is still there."""
        with self._lock:
            adopted = [job for job in self._jobs if job.pid is not None and job.is_running]
        for job in adopted:
            if not is_alive(job.pid):
                with self._lock:
                    job.status = DONE
                    job.percent = 100.0
                    job.finished_at = time.monotonic()

    def running_pids(self) -> list[int]:
        with self._lock:
            return [job.pid for job in self._jobs if job.is_running and job.pid is not None]

    def jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs)

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs if job.is_running)

    def summary(self) -> str:
        """A line for the menu card, or nothing when there is nothing to say."""
        with self._lock:
            if not self._jobs:
                return ""
            running = sum(1 for job in self._jobs if job.is_running)
            finished = len(self._jobs) - running

        parts = []
        if running:
            parts.append(f"{running} running")
        if finished:
            parts.append(f"{finished} finished")
        return ", ".join(parts)

    def clear_finished(self) -> None:
        with self._lock:
            keep = [job for job in self._jobs if job.is_running]
            for job in self._jobs:
                if not job.is_running:
                    self._events.pop(job.id, None)
                    self._threads.pop(job.id, None)
            self._jobs = keep

    def wait_for(self, job_id: int, timeout: float | None = None) -> bool:
        with self._lock:
            event = self._events.get(job_id)
        return event.wait(timeout) if event else True

    def wait_all(self, timeout: float | None = None) -> None:
        with self._lock:
            threads = list(self._threads.values())
        for thread in threads:
            thread.join(timeout)
