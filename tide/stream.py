"""Task streams: continual-learning evaluation over a sequence of episodes.

A :class:`Stream` is an ordered list of Harbor tasks run under one agent,
with a **state directory** carried from episode to episode. Each position
is one ordinary episode — one Harbor trial, one container, one trusted
row — and the only thing connecting the positions is whatever the agent
wrote into ``$TIDE_STATE_DIR``: memory files, a skill library, an evolved
harness. Whether accumulating that state actually helps is the
measurement.

Mechanics per position:

- the state directory is delivered by the executor (bind-mounted into the
  agent's container; a host path under ``--local``) — see
  :mod:`tide.executors`;
- **before** the episode runs, the live state is reset from the previous
  position's snapshot, so every episode's starting state is deterministic
  even across crashes and re-runs;
- **after** it runs, the state is snapshotted
  (``<lab>/streams/<stream>-<variant>/snapshots/<position>``), which is
  what makes resume honest and every episode's input state auditable.

Episodes land in the same store as everything else, tagged ``stream`` and
``position``; the continual-learning metrics
(:func:`tide.metrics.learning_curve`, :func:`tide.metrics.transfer`,
:func:`tide.metrics.forgetting`) are queries over those tags.

Resume follows the Lab's rule — re-running skips recorded positions — with
one stream-specific refinement: a position's key covers the task list *up
to that position*. Appending tasks therefore extends a finished stream,
while editing an earlier position re-runs everything after it: a stream is
one measurement, and a changed history invalidates what followed.

To seed a stream with pre-built state (an agent that already has a
memory), copy it into ``<state_root>/state`` before the first run — see
:meth:`Stream.state_root`. The seed is captured once as the ``init``
snapshot. A stream's state is agent-authored and untrusted; it is never
visible to any judge or verifier, so it can influence only the agent's own
future — the trust model is unchanged.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tide.budget import Budget
from tide.types import Row, Tags

if TYPE_CHECKING:
    from tide.lab import Lab

logger = logging.getLogger("tide")


class Stream:
    """An ordered task sequence evaluated under one carried agent state."""

    def __init__(self, name: str, tasks: Sequence[str]):
        if not tasks:
            raise ValueError("a stream needs at least one task")
        self.name = name
        self.tasks = list(tasks)

    async def run(
        self,
        lab: Lab,
        agent: dict[str, Any],
        *,
        tags: Tags | None = None,
        budget: Budget | dict[str, Any] | float | int | str | None = None,
        **overrides: Any,
    ) -> list[Row]:
        """Run every position in order, carrying state; one Row per position.

        Sequential by design: position p+1's starting state is position p's
        ending state, so a stream is one measurement, not a batch. (Distinct
        streams run concurrently just fine; never run the *same* stream
        variant concurrently with itself.) Already-recorded positions are
        skipped, and their snapshots stand in for re-execution.

        ``agent``, ``budget``, and ``**overrides`` mean exactly what they
        mean on :meth:`tide.lab.Lab.run` and apply to every position;
        ``tags`` are recorded on every row, plus ``stream`` and ``position``.
        """
        tags = dict(tags or {})
        budget = Budget.coerce(budget)
        variant = self._variant(agent, tags, budget, overrides)
        root = self._root(lab, variant)
        live = root / "state"
        snapshots = root / "snapshots"

        rows: list[Row] = []
        prev_snap: Path | None = None
        for position, task in enumerate(self.tasks):
            key = self._key(position, task, variant)
            snap = snapshots / f"{position:03d}"
            if (existing := lab.store.get(key)) is not None:
                logger.info("skip %s (already recorded)", key)
                rows.append(existing)
                prev_snap = snap
                continue
            self._reset_state(live, prev_snap, init=snapshots / "init")
            row = await lab.run(
                task,
                agent,
                tags={**tags, "stream": self.name, "position": position},
                budget=budget,
                key=key,
                state_dir=str(live),
                **overrides,
            )
            _copy_dir(live, snap)
            rows.append(row)
            prev_snap = snap
        return rows

    def state_root(
        self,
        lab: Lab,
        agent: dict[str, Any],
        *,
        tags: Tags | None = None,
        budget: Budget | dict[str, Any] | float | int | str | None = None,
        **overrides: Any,
    ) -> Path:
        """Where this stream variant keeps its state, for the same arguments
        you would pass to :meth:`run`: ``<state_root>/state`` is the live
        directory (write here before the first run to seed the stream) and
        ``<state_root>/snapshots/<position>`` is each episode's ending state.
        """
        variant = self._variant(
            agent, dict(tags or {}), Budget.coerce(budget), overrides
        )
        return self._root(lab, variant)

    # -------------------------------------------------------------- helpers

    def _root(self, lab: Lab, variant: str) -> Path:
        return lab.root / "streams" / f"{self.name}-{variant}"

    def _variant(
        self,
        agent: dict[str, Any],
        tags: Tags,
        budget: Budget | None,
        overrides: dict[str, Any],
    ) -> str:
        """One digest per distinct measurement setup, so the same stream name
        under two agents (or budgets) keeps separate state and separate keys."""
        from tide.lab import Lab

        return Lab._digest(
            {
                "agent": agent,
                "tags": tags,
                "budget": None if budget is None else budget.to_tags(),
                "overrides": overrides,
            }
        )

    def _key(self, position: int, task: str, variant: str) -> str:
        """Stable episode key covering the task list up to this position, so
        appends extend a stream while edits invalidate their suffix."""
        from tide.lab import Lab

        prefix = Lab._digest({"variant": variant, "prefix": self.tasks[: position + 1]})
        short = task.rstrip("/").split("/")[-1]
        return f"{self.name}@{position:03d}:{short}:{prefix}"

    @staticmethod
    def _reset_state(live: Path, prev_snap: Path | None, *, init: Path) -> None:
        """live := the previous position's snapshot (the seed for position 0)."""
        if prev_snap is None:
            # Position 0: whatever the live dir holds before the first run is
            # the stream's seed state; capture it once as the init snapshot.
            if not init.is_dir():
                live.mkdir(parents=True, exist_ok=True)
                _copy_dir(live, init)
            prev_snap = init
        elif not prev_snap.is_dir():
            # The previous position has a row but no snapshot: a crash in the
            # window after its row was stored. Nothing ran since, so the live
            # dir is exactly its ending state — recover the snapshot from it.
            if not live.is_dir():
                raise RuntimeError(
                    f"cannot resume stream: snapshot {prev_snap} is missing and "
                    f"there is no live state at {live} to recover it from"
                )
            logger.warning("recovering missing snapshot %s from live state", prev_snap)
            _copy_dir(live, prev_snap)
        if live.exists():
            shutil.rmtree(live)
        _copy_dir(prev_snap, live)


def _copy_dir(src: Path, dst: Path) -> None:
    """Copy a directory such that a crash never leaves a half-written *dst*
    (copy to a sibling, then rename into place)."""
    tmp = dst.with_name(dst.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, tmp)
    if dst.exists():
        shutil.rmtree(dst)
    tmp.rename(dst)
