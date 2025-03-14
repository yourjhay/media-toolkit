"""Running one operation across many files and tallying the outcome."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .core import FAILED, Result

Operation = Callable[[Path], Result]
ProgressHook = Callable[[Result], None]


@dataclass
class Summary:
    results: list[Result] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return dict(Counter(r.status for r in self.results))

    @property
    def bytes_saved(self) -> int:
        return sum(r.bytes_saved for r in self.results)

    def of_status(self, status: str) -> list[Result]:
        return [r for r in self.results if r.status == status]


def run_batch(
    paths: list[Path],
    operation: Operation,
    on_progress: ProgressHook | None = None,
) -> Summary:
    """Apply `operation` to each path, collecting results rather than stopping.

    A crash in one file is recorded as a failed result and the batch continues;
    losing a whole run of 400 photos to one corrupt file would be worse than
    reporting the one that broke.
    """
    summary = Summary()
    for path in paths:
        try:
            result = operation(path)
        except Exception as exc:
            result = Result(path, None, FAILED, detail=f"{type(exc).__name__}: {exc}")
        summary.results.append(result)
        if on_progress is not None:
            on_progress(result)
    return summary
