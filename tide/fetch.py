"""Fetch stock Harbor tasks from a benchmark's pinned git commit.

The continual-learning stream benchmarks (terminal-bench 2.0, SWE-bench
Verified) publish their tasks as ordinary Harbor task directories in a git
repository, and the Harbor registry pins each release to one exact commit.
Fetching is therefore not a conversion: a shallow fetch of that commit,
then copying the wanted task folders out. The pin is what makes a fetch
reproducible — the same ``fetch.py`` yields the same tasks, always.

Blobs are fetched lazily (``--filter=blob:none``) and only the selected
task folders are checked out, so pulling a handful of tasks from a huge
dataset repository downloads roughly those tasks and nothing else.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def fetch_pinned_tasks(
    git_url: str,
    commit: str,
    dest: Path | str,
    *,
    subdir: str = "",
    only: list[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    """Copy the task folders published at ``git_url@commit`` into *dest*.

    A task folder is any directory directly under *subdir* (the repo root
    by default) containing a ``task.toml``. ``only`` restricts the fetch to
    the named tasks and raises on names that don't exist at the pin;
    ``limit`` keeps the first N alphabetically. Existing copies in *dest*
    are replaced. Returns the copied names, sorted.
    """
    dest = Path(dest)
    prefix = f"{subdir.rstrip('/')}/" if subdir else ""
    with tempfile.TemporaryDirectory(prefix="tide-fetch-") as tmp_str:
        tmp = Path(tmp_str)
        _git(tmp, "init", "-q")
        _git(tmp, "remote", "add", "origin", git_url)
        _git(tmp, "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", commit)

        listing = _git(tmp, "ls-tree", "-r", "--name-only", commit)
        names = sorted(
            {
                rest.split("/", 1)[0]
                for line in listing.splitlines()
                if line.startswith(prefix)
                and (rest := line[len(prefix) :]).count("/") == 1
                and rest.endswith("/task.toml")
            }
        )
        if not names:
            raise RuntimeError(
                f"no task folders under '{subdir or '.'}' at {git_url}@{commit[:12]}"
            )
        if only:
            unknown = sorted(set(only) - set(names))
            if unknown:
                raise ValueError(
                    f"unknown task(s) {unknown}; the pin has {len(names)} tasks: "
                    f"{', '.join(names[:8])}, ..."
                )
            wanted = set(only)
            names = [n for n in names if n in wanted]
        if limit is not None:
            names = names[:limit]

        _git(tmp, "checkout", "-q", commit, "--", *(f"{prefix}{n}" for n in names))
        dest.mkdir(parents=True, exist_ok=True)
        for name in names:
            src = (tmp / subdir / name) if subdir else (tmp / name)
            target = dest / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
    return names


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode:
        raise RuntimeError(f"git {args[0]} failed: {proc.stderr.strip()[-500:]}")
    return proc.stdout
