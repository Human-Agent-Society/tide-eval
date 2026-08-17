"""Fetch stock Harbor tasks from a benchmark's pinned git commit.

Stream benchmarks publish their tasks as ordinary Harbor task directories
in a git repository, pinned to one commit. Fetching is a shallow fetch of
that commit plus copying the wanted task folders out — no conversion.
Blobs are fetched lazily, so pulling a few tasks from a large dataset
repository downloads roughly those tasks and nothing else.
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
    by default) containing a ``task.toml``. ``only`` restricts the fetch
    to the named tasks and raises on unknown names; ``limit`` keeps the
    first N alphabetically. Existing copies in *dest* are replaced.
    Returns the copied names, sorted.
    """
    dest = Path(dest)
    prefix = f"{subdir.rstrip('/')}/" if subdir else ""
    with tempfile.TemporaryDirectory(prefix="tide-fetch-") as tmp_str:
        tmp = Path(tmp_str)
        _git(tmp, "init", "-q")
        _git(tmp, "remote", "add", "origin", git_url)
        print(f"fetching {git_url} @ {commit[:12]} ...", flush=True)
        _git(tmp, "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", commit)

        found: set[str] = set()
        for line in _git(tmp, "ls-tree", "-r", "--name-only", commit).splitlines():
            if not line.startswith(prefix):
                continue
            rest = line[len(prefix) :]
            if rest.count("/") == 1 and rest.endswith("/task.toml"):
                found.add(rest.split("/", 1)[0])
        names = sorted(found)
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
            names = [n for n in names if n in set(only)]
        if limit is not None:
            names = names[:limit]

        print(f"copying {len(names)} task folder(s) ...", flush=True)
        _git(tmp, "checkout", "-q", commit, "--", *(prefix + n for n in names))
        dest.mkdir(parents=True, exist_ok=True)
        for name in names:
            src = tmp / subdir / name if subdir else tmp / name
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
