"""The Lab: tide's one public surface.

A Lab is a directory. Inside it live the results database (``results.sqlite``)
and, when the Harbor executor is used, the Harbor trial directories
(``trials/``). Everything a Lab ever does is:

- ``run()``   — execute one episode (a Harbor task under an agent), store the
  trusted reward plus the judge's submission log, and skip work that
  already has a stored result.
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
        concurrency: int = 4,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

        from tide.store import Store

        self.store = Store(self.root / "results.sqlite")
        self.executor: Executor = executor or HarborExecutor(self.root / "trials")
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

        ``key`` is the episode's stable ID; when omitted it is derived from
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
            tags={
                **tags,
                **result.usage,
                **({"error": result.error} if result.error else {}),
            },
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
        # Normalize a filesystem-path task to its canonical absolute form so
        # that "tasks/x", "tasks/x/", and an absolute path all key to one
        # episode (otherwise resume silently re-runs). Harbor registry ids
        # (non-paths) are hashed verbatim.
        task_path = Path(spec.task)
        task_id = str(task_path.resolve()) if task_path.exists() else spec.task
        digest = cls._digest(
            {
                "task": task_id,
                "agent": spec.agent,
                "tags": tags,
                "overrides": spec.overrides,
            }
        )
        short_task = spec.task.rstrip("/").split("/")[-1]
        return f"{short_task}:{digest}"
