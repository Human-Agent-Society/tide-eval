"""Locating the tasks catalog.

The catalog is a directory tree, not package data, so it is found rather
than imported — in order: an explicit argument, the ``TIDE_TASKS_DIR``
environment variable, ``./tasks`` under the current directory, and the
checkout the tide package itself lives in.
"""

from __future__ import annotations

import os
from pathlib import Path


def find_tasks_root(explicit: str | None = None) -> Path | None:
    if explicit:
        return Path(explicit)
    env = os.environ.get("TIDE_TASKS_DIR")
    if env:
        return Path(env)
    for base in (Path.cwd(), Path(__file__).parent.parent):
        candidate = base / "tasks"
        if candidate.is_dir():
            return candidate
    return None


def resolve_bench(relative: str, explicit: str | None = None) -> Path:
    root = find_tasks_root(explicit)
    if root is None or not (root / relative).exists():
        raise FileNotFoundError(
            f"cannot locate 'tasks/{relative}' — run from a tide checkout, or "
            "set TIDE_TASKS_DIR to a tasks catalog"
        )
    return root / relative
