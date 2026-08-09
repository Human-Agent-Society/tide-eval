"""The Lab: tide's one public surface.

A Lab is a directory. Inside it live the results database (``results.sqlite``)
and, when the Harbor executor is used, the Harbor trial directories
(``trials/``). Everything a Lab ever does is:

- ``run()``   — execute one episode (a Harbor task under an agent), store the
  trusted reward plus any untrusted score trajectory, and skip work whose
  idempotency key already has a result.
- ``probe()`` — one direct-inference measurement judged against rubrics
  (no container; see :mod:`tide.probe`).
- ``df()``    — everything as a pandas DataFrame; metrics are queries.

Persistence lives in the data: there is no daemon, and re-running a crashed
script resumes it because completed keys are skipped.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from tide.executors import Executor, HarborExecutor
from tide.types import EpisodeSpec, Row, Tags

logger = logging.getLogger("tide")


class Lab:
    def __init__(
        self,
        root: Path | str,
        *,
        executor: Executor | None = None,
        prober: Any | None = None,
        concurrency: int = 4,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

        from tide.store import Store

        self.store = Store(self.root / "results.sqlite")
        self.executor: Executor = executor or HarborExecutor(self.root / "trials")
        self.prober = prober
        self._semaphore = asyncio.Semaphore(concurrency)

    # ------------------------------------------------------------- episodes

    async def run(
        self,
        task: str,
        agent: dict[str, Any],
        *,
        tags: Tags | None = None,
        key: str | None = None,
        **overrides: Any,
    ) -> Row:
        """Run one episode and store its trusted result.

        ``key`` is the idempotency key; when omitted it is derived from
        (task, agent, tags), so identical calls are one episode. If the key
        already has a stored row, that row is returned and nothing runs.
        ``overrides`` pass through to the executor (for Harbor: TrialConfig
        fields such as ``verifier=...`` or ``timeout_multiplier=...``).
        """
        tags = dict(tags or {})
        spec = EpisodeSpec(task=task, agent=dict(agent), overrides=dict(overrides))
        key = key or self._default_key(spec, tags)

        if (existing := self.store.get(key)) is not None:
            logger.info("skip %s (already recorded)", key)
            return existing

        async with self._semaphore:
            # A retried episode may have left trace rows behind; clear them so
            # the trace is never double-recorded.
            self.store.delete_prefix(f"{key}#")
            result = await self.executor.execute(spec)

        for i, point in enumerate(result.trace):
            self.store.put(
                Row(
                    key=f"{key}#t{i}",
                    kind="trace",
                    task=task,
                    tags={**tags, "t": point.t, **point.data},
                    rewards={"score": point.score},
                    uri=result.uri,
                )
            )

        row = Row(
            key=key,
            kind="episode",
            task=task,
            tags={**tags, **({"error": result.error} if result.error else {})},
            rewards=dict(result.rewards),
            uri=result.uri,
        )
        self.store.put(row)
        return row

    async def run_many(self, calls: list[dict[str, Any]]) -> list[Row]:
        """Run many episodes concurrently (bounded by the Lab's concurrency).

        Each entry is a kwargs dict for :meth:`run`. Order of results matches
        the order of calls.
        """
        return list(await asyncio.gather(*(self.run(**call) for call in calls)))

    # --------------------------------------------------------------- probes

    async def probe(
        self,
        probe: Any,
        model: dict[str, Any] | None = None,
        *,
        tags: Tags | None = None,
        key: str | None = None,
    ) -> Row:
        """Run one direct-inference probe (see :mod:`tide.probe`).

        Requires the Lab to be constructed with a ``prober``; kept separate
        from ``run()`` because probes are API-cheap and containerless, which
        is what makes dense per-phase measurement affordable.
        """
        if self.prober is None:
            raise RuntimeError(
                "This Lab has no prober. Construct it with "
                "Lab(root, prober=ProbeExecutor(...))."
            )
        tags = dict(tags or {})
        key = key or "probe:" + self._digest(
            {"probe": getattr(probe, "id", repr(probe)), "model": model, "tags": tags}
        )
        if (existing := self.store.get(key)) is not None:
            logger.info("skip %s (already recorded)", key)
            return existing

        async with self._semaphore:
            rewards = await self.prober.execute(probe, model or {})

        row = Row(
            key=key,
            kind="probe",
            task=getattr(probe, "id", repr(probe)),
            tags=tags,
            rewards=rewards,
        )
        self.store.put(row)
        return row

    # -------------------------------------------------------------- queries

    def df(self, kind: str | None = None) -> pd.DataFrame:
        return self.store.df(kind)

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _digest(obj: Any) -> str:
        blob = json.dumps(obj, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    @classmethod
    def _default_key(cls, spec: EpisodeSpec, tags: Tags) -> str:
        digest = cls._digest(
            {
                "task": spec.task,
                "agent": spec.agent,
                "tags": tags,
                "overrides": spec.overrides,
            }
        )
        short_task = spec.task.rstrip("/").split("/")[-1]
        return f"{short_task}:{digest}"
