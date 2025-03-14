"""Remembering small preferences between runs.

Only conveniences live here — the folder someone last saved to, and the like.
Nothing depends on this file existing or being readable, so a missing or
damaged one costs a default, never a run.
"""

from __future__ import annotations

import json
from pathlib import Path


def default_store() -> Path:
    return Path.home() / ".config" / "rj-toolkit" / "settings.json"


def _load(store: Path) -> dict:
    try:
        data = json.loads(store.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save(store: Path, data: dict) -> None:
    try:
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps(data, indent=2, sort_keys=True))
    except Exception:
        pass  # a lost preference must never take a finished job with it


def remember_path(key: str, value: Path, store: Path | None = None) -> None:
    store = store or default_store()
    data = _load(store)
    data[key] = str(value)
    _save(store, data)


def recall_path(key: str, fallback: Path, store: Path | None = None) -> Path:
    """The remembered path for `key`, or `fallback`.

    A remembered folder that has since been deleted is still offered: it is the
    default in a prompt, not a promise, and the user can edit it.
    """
    store = store or default_store()
    value = _load(store).get(key)
    return Path(value) if isinstance(value, str) and value else fallback
