"""Stream tooling: the state directory and the weight-plane contract.

A stream is an ordered sequence of episodes where **one folder of state is the
only thing allowed to cross episode boundaries**. tide does not ship a stream
"runner" — protocols are Python scripts (see the README's stream example),
because feedback policies, probe sampling, and orderings are natural ``if``s
and ``for``s, and a DSL would grow fields forever. What tide ships is the
state machinery those scripts need:

- :class:`StateDir` — a directory versioned with git. ``snapshot()`` freezes
  the current contents into a ref; ``materialize(ref)`` re-creates any
  historical version (required for matrices: "re-probe task 7 with the state
  the learner had at phase 3"). The history doubles as an audit trail: diff
  two refs to see exactly what the learner carried forward.
- :class:`WeightPlane` — the two-method, vendor-neutral contract tide demands
  of a serving stack when the evolving state is model weights instead of
  files. reef implements it; so does vLLM plus a checkpoint directory; a
  static model implements it trivially.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol


class WeightPlane(Protocol):
    """Everything tide requires of a weight-serving stack.

    ``snapshot`` freezes the currently-served weights and returns a durable
    version reference. ``serve`` makes any previously-snapshotted version
    reachable again and returns an OpenAI-compatible base URL for it.
    """

    def snapshot(self) -> str: ...
    def serve(self, ref: str) -> str: ...


class StaticWeightPlane:
    """The trivial WeightPlane: a model that never learns.

    Useful as the fresh-control arm when computing gain, and as the reference
    implementation of the contract.
    """

    def __init__(self, base_url: str, ref: str = "static"):
        self._base_url = base_url
        self._ref = ref

    def snapshot(self) -> str:
        return self._ref

    def serve(self, ref: str) -> str:
        if ref != self._ref:
            raise KeyError(
                f"unknown ref {ref!r}; static plane only serves {self._ref!r}"
            )
        return self._base_url


class StateDir:
    """A git-versioned state folder — the stream's single crossing channel."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        if not (self.path / ".git").is_dir():
            self._git("init", "-q")
            self._git("config", "user.email", "tide@localhost")
            self._git("config", "user.name", "tide")

    def snapshot(self, message: str = "snapshot") -> str:
        """Commit the current contents and return the commit hash (the ref).

        Idempotent when nothing changed: returns the existing HEAD.
        """
        self._git("add", "-A")
        status = self._git("status", "--porcelain")
        if status.strip():
            self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "HEAD").strip()

    def materialize(self, ref: str, dest: Path | str | None = None) -> Path:
        """Re-create the state as of *ref* in a fresh directory (never the
        live one), so historical probes can't disturb the evolving state."""
        dest = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="tide-state-"))
        dest.mkdir(parents=True, exist_ok=True)
        archive = self._git("archive", "--format=tar", ref, capture_bytes=True)
        subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
        return dest

    def refs(self) -> list[str]:
        """All snapshot refs, oldest first."""
        out = self._git("log", "--format=%H", "--reverse")
        return [line for line in out.splitlines() if line]

    def diff(self, ref_a: str, ref_b: str) -> str:
        """What changed between two snapshots — the audit trail."""
        return self._git("diff", ref_a, ref_b)

    def destroy(self) -> None:
        shutil.rmtree(self.path)

    def _git(self, *args: str, capture_bytes: bool = False):
        result = subprocess.run(
            ["git", "-C", str(self.path), *args],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace')}"
            )
        return result.stdout if capture_bytes else result.stdout.decode()
