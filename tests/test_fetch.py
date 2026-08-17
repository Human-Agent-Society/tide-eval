"""fetch_pinned_tasks: pinned-commit fetching, tested against a local git repo."""

import subprocess
from pathlib import Path

import pytest

from tide.fetch import fetch_pinned_tasks


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture()
def upstream(tmp_path):
    """A local 'published benchmark' repo: two root tasks, one nested dataset
    task, and a non-task folder that must never be copied."""
    repo = tmp_path / "upstream"
    for name in ("alpha", "beta"):
        (repo / name).mkdir(parents=True)
        (repo / name / "task.toml").write_text(f'name = "{name}"\n')
        (repo / name / "instruction.md").write_text("do the thing\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "notes.md").write_text("not a task\n")
    (repo / "datasets" / "swe" / "gamma").mkdir(parents=True)
    (repo / "datasets" / "swe" / "gamma" / "task.toml").write_text('name = "gamma"\n')
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    # What GitHub allows, granted locally: fetch by SHA, with a blob filter.
    _git(repo, "config", "uploadpack.allowAnySHA1InWant", "true")
    _git(repo, "config", "uploadpack.allowFilter", "true")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pin")
    sha = _git(repo, "rev-parse", "HEAD").strip()
    return f"file://{repo}", sha


def test_fetches_root_tasks_and_skips_non_tasks(upstream, tmp_path):
    url, sha = upstream
    dest = tmp_path / "dest"
    assert fetch_pinned_tasks(url, sha, dest) == ["alpha", "beta"]
    assert (dest / "alpha" / "instruction.md").exists()
    assert not (dest / "docs").exists()  # no task.toml
    assert not (dest / "datasets").exists()  # nested — not a root task


def test_subdir_scopes_the_scan(upstream, tmp_path):
    url, sha = upstream
    dest = tmp_path / "dest"
    assert fetch_pinned_tasks(url, sha, dest, subdir="datasets/swe") == ["gamma"]
    assert (dest / "gamma" / "task.toml").exists()


def test_only_selects_and_unknown_names_are_loud(upstream, tmp_path):
    url, sha = upstream
    dest = tmp_path / "dest"
    assert fetch_pinned_tasks(url, sha, dest, only=["beta"]) == ["beta"]
    assert not (dest / "alpha").exists()
    with pytest.raises(ValueError, match="unknown task"):
        fetch_pinned_tasks(url, sha, dest, only=["nope"])


def test_limit_keeps_the_first_n(upstream, tmp_path):
    url, sha = upstream
    assert fetch_pinned_tasks(url, sha, tmp_path / "dest", limit=1) == ["alpha"]


def test_refetch_replaces_local_edits(upstream, tmp_path):
    url, sha = upstream
    dest = tmp_path / "dest"
    fetch_pinned_tasks(url, sha, dest)
    (dest / "alpha" / "task.toml").write_text("tampered = true\n")
    fetch_pinned_tasks(url, sha, dest)
    assert (dest / "alpha" / "task.toml").read_text() == 'name = "alpha"\n'


def test_empty_scope_is_loud(upstream, tmp_path):
    url, sha = upstream
    with pytest.raises(RuntimeError, match="no task folders"):
        fetch_pinned_tasks(url, sha, tmp_path / "dest", subdir="docs")


# ---------------------------------------------------------- benchmark cache


def _benchmark_upstream(tmp_path):
    """A local stand-in for the tide repo: one benchmark with one task."""
    repo = tmp_path / "tide-repo"
    task = repo / "tasks" / "autoresearch" / "first-party" / "alpha"
    task.mkdir(parents=True)
    (task / "task.toml").write_text('name = "alpha"\n')
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "uploadpack.allowAnySHA1InWant", "true")
    _git(repo, "config", "uploadpack.allowFilter", "true")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pin")
    return repo


def test_benchmark_downloads_once_then_caches(tmp_path, monkeypatch):
    from tide import fetch

    repo = _benchmark_upstream(tmp_path)
    sha = _git(repo, "rev-parse", "HEAD").strip()
    monkeypatch.setenv("TIDE_TASKS_REPO", f"file://{repo}")
    monkeypatch.setenv("TIDE_TASKS_REF", sha)
    monkeypatch.setenv("TIDE_CACHE", str(tmp_path / "cache"))

    dest = fetch.benchmark("first-party")
    assert (dest / "alpha" / "task.toml").exists()
    assert str(tmp_path / "cache") in str(dest) and sha in str(dest)

    # Second call is served from the cache: works even without the source.
    import shutil

    shutil.rmtree(repo)
    assert fetch.benchmark("first-party") == dest


def test_benchmark_unknown_name_is_loud():
    from tide import fetch

    with pytest.raises(ValueError, match="unknown benchmark"):
        fetch.benchmark("nope")


def test_resolve_targets_downloads_known_benchmarks(tmp_path, monkeypatch):
    from tide import fetch
    from tide.cli import resolve_targets

    bench = tmp_path / "bench"
    (bench / "alpha").mkdir(parents=True)
    (bench / "alpha" / "task.toml").write_text('name = "alpha"\n')
    monkeypatch.setattr(fetch, "benchmark", lambda name: bench)

    assert resolve_targets(["first-party"], None) == [str(bench / "alpha")]
    assert resolve_targets(["first-party/alpha"], None) == [str(bench / "alpha")]
    # Unregistered names still pass through as Harbor registry ids.
    assert resolve_targets(["org/some-task"], None) == ["org/some-task"]
