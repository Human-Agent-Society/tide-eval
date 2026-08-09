"""Episode executors.

An executor turns an :class:`EpisodeSpec` into an :class:`EpisodeResult`.
The Lab doesn't care how — that indirection is what keeps the core testable
without Docker and lets the same orchestration drive containers today and
anything else later.

- :class:`HarborExecutor` — the real one: builds a Harbor ``TrialConfig``,
  runs ``Trial``, returns the verifier's rewards plus the ingested score
  trajectory. Harbor is imported lazily so the rest of tide works without it.
- :class:`FakeExecutor` — deterministic, instant, dependency-free. Used by the
  test suite and the quickstart demo.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from tide.trajectory import load_trace
from tide.types import EpisodeResult, EpisodeSpec


class Executor(Protocol):
    async def execute(self, spec: EpisodeSpec) -> EpisodeResult: ...


class HarborExecutor:
    """Runs episodes as Harbor trials.

    ``trials_dir`` is where Harbor writes trial directories (one per episode);
    each stored row's ``uri`` points into it. ``agent`` dicts use Harbor's
    ``AgentConfig`` field names verbatim; ``spec.overrides`` maps onto
    ``TrialConfig`` fields (e.g. ``{"verifier": {"disable": True}}`` or
    ``{"timeout_multiplier": 2.0}``).
    """

    def __init__(self, trials_dir: Path | str):
        self.trials_dir = Path(trials_dir)

    async def execute(self, spec: EpisodeSpec) -> EpisodeResult:
        # Lazy import: Harbor's dependency tree is heavy and optional.
        from harbor.models.trial.config import TaskConfig, TrialConfig
        from harbor.trial.trial import Trial

        task_field = (
            {"path": Path(spec.task)}
            if Path(spec.task).exists()
            else {"name": spec.task}
        )
        config = TrialConfig.model_validate(
            {
                "task": TaskConfig.model_validate(task_field).model_dump(),
                "trials_dir": self.trials_dir,
                "agent": dict(spec.agent),
                **spec.overrides,
            }
        )

        trial = await Trial.create(config)
        result = await trial.run()

        rewards = result.verifier_result.rewards if result.verifier_result else {}
        error = (
            result.exception_info.exception_message
            if result.exception_info is not None
            else None
        )
        return EpisodeResult(
            rewards=dict(rewards),
            uri=result.trial_uri,
            trace=tuple(load_trace(trial.paths.artifacts_dir)),
            error=error,
        )


class FakeExecutor:
    """Deterministic executor for tests and demos.

    ``score`` maps a spec to rewards; the default scores by a stable hash of
    the task name so demos produce varied but reproducible numbers. ``trace``
    optionally fabricates a score trajectory per spec.
    """

    def __init__(
        self,
        score: Callable[[EpisodeSpec], dict[str, Any]] | None = None,
        trace: Callable[[EpisodeSpec], list] | None = None,
    ):
        self._score = score or self._default_score
        self._trace = trace
        self.calls: list[EpisodeSpec] = []

    async def execute(self, spec: EpisodeSpec) -> EpisodeResult:
        self.calls.append(spec)
        return EpisodeResult(
            rewards=self._score(spec),
            uri=f"fake://{spec.task}",
            trace=tuple(self._trace(spec)) if self._trace else (),
        )

    @staticmethod
    def _default_score(spec: EpisodeSpec) -> dict[str, float]:
        digest = sum(spec.task.encode()) % 100
        return {"reward": round(digest / 100, 2)}
