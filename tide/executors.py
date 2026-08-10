"""Episode executors.

An executor turns an :class:`EpisodeSpec` into an :class:`EpisodeResult`.
The Lab doesn't care how — that indirection is what keeps the core testable
without Docker and lets the same orchestration drive containers today and
anything else later.

- :class:`HarborExecutor` — the benchmark run: containers, isolated
  verifier. Harbor is imported lazily so the rest of tide works without it.
- :class:`LocalExecutor` — the development run: the real scorer and grader
  on this machine, no containers.
- :class:`FakeExecutor` — deterministic, instant, dependency-free. Used by
  the test suite and the quickstart demo.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import subprocess
import tempfile
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from tide.score_log import load_trace
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


class LocalExecutor:
    """Runs episodes on this machine — real scorer, real grader, no Docker.

    The task contract is identical to the container run, with one
    substitution: ``APP`` is a temp directory on the host instead of
    ``/app``. Your command finds ``scorer.py`` at ``$APP/scorer.py``, writes
    its best solution to ``$APP/best/solution.json``, and gets its time
    budget as ``$BUDGET_SEC``; being killed at the deadline is a normal
    ending. Afterwards ``tests/grade.py`` is imported and called directly on
    the artifact.

    This is the development loop: fast, dependency-free, and honest about
    what it is — nothing is isolated, so every row's ``uri`` says
    ``local://`` and local numbers should never be reported as benchmark
    results. Works for any task that follows the template layout
    (``environment/scorer.py`` + ``tests/grade.py``); image-based tasks
    (EdgeBench, FrontierCS) need containers.

    ``spec.agent`` needs a ``command`` (a shell command — the CLI flag is
    ``--command``) and may carry ``override_timeout_sec``; otherwise the
    budget comes from the task's ``[agent] timeout_sec``.
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else None
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)

    async def execute(self, spec: EpisodeSpec) -> EpisodeResult:
        task_dir = Path(spec.task)
        scorer = task_dir / "environment" / "scorer.py"
        grader_path = task_dir / "tests" / "grade.py"
        if not (scorer.is_file() and grader_path.is_file()):
            return EpisodeResult(
                rewards={},
                error=f"{spec.task} does not follow the template layout "
                "(environment/scorer.py + tests/grade.py) — run it in containers",
            )
        command = spec.agent.get("command")
        if not command:
            return EpisodeResult(
                rewards={},
                error='local runs need agent={"command": "..."} '
                "(the CLI flag is --command)",
            )

        budget = spec.agent.get("override_timeout_sec")
        if budget is None:
            config = tomllib.loads((task_dir / "task.toml").read_text())
            budget = config.get("agent", {}).get("timeout_sec", 600.0)

        workdir = Path(tempfile.mkdtemp(prefix=f"{task_dir.name}-", dir=self.root))
        for item in (task_dir / "environment").iterdir():
            if item.name == "Dockerfile":
                continue
            if item.is_dir():
                shutil.copytree(item, workdir / item.name)
            else:
                shutil.copy(item, workdir / item.name)
        (workdir / "best").mkdir(exist_ok=True)

        error = None
        try:
            # The command runs from the caller's cwd (so its relative paths
            # work); the task's files are reached through $APP.
            proc = await asyncio.to_thread(
                subprocess.run,
                command,
                shell=True,
                env={**os.environ, "APP": str(workdir), "BUDGET_SEC": str(budget)},
                timeout=float(budget),
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                error = f"agent command exited {proc.returncode}: {proc.stderr[-500:]}"
        except subprocess.TimeoutExpired:
            pass  # budget spent — a normal ending

        artifact = workdir / "best" / "solution.json"
        grade = self._load_grader(grader_path, workdir.name)
        result = grade(artifact if artifact.exists() else None)
        return EpisodeResult(
            rewards={"reward": float(result["reward"])},
            uri=f"local://{workdir}",
            trace=tuple(load_trace(workdir)),
            error=error,
        )

    @staticmethod
    def _load_grader(grader_path: Path, unique: str):
        spec = importlib.util.spec_from_file_location(f"grade_{unique}", grader_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.grade


class FakeExecutor:
    """Deterministic executor for tests and demos.

    ``score`` maps a spec to rewards; the default scores by a stable hash of
    the task name so demos produce varied but reproducible numbers. ``trace``
    optionally fabricates a score log per spec.
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
