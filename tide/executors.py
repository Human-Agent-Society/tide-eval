"""Episode executors.

An executor turns an :class:`EpisodeSpec` into an :class:`EpisodeResult`.
The Lab doesn't care how — that indirection is what keeps the core testable
without Docker and lets the same orchestration drive containers today and
anything else later.

- :class:`HarborExecutor` — the benchmark run: containers, judge sidecar,
  verifier. Harbor is imported lazily so the rest of tide works without it.
- :class:`LocalExecutor` — the development run: the task's real judge as a
  local process, no containers.
- :class:`FakeExecutor` — deterministic, instant, dependency-free. Used by
  the test suite and the quickstart demo.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from tide.submissions import load_trace
from tide.types import EpisodeResult, EpisodeSpec, TracePoint


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
        trace = tuple(load_trace(trial.paths.trial_dir))
        return EpisodeResult(
            rewards=dict(rewards),
            uri=result.trial_uri,
            trace=trace,
            error=error,
            usage=_harbor_usage(result.agent_result, len(trace)),
        )


def _harbor_usage(agent_result: Any, n_submissions: int) -> dict[str, float]:
    """Pull the harness's own token/cost accounting off Harbor's AgentContext.

    These numbers come from each adapter parsing its harness's usage report
    (claude-code / codex / qwen trajectories), so they are as accurate as the
    provider's bill — the right signal even for closed models. Absent fields
    are simply omitted.
    """
    usage: dict[str, float] = {"n_submissions": float(n_submissions)}
    if agent_result is None:
        return usage
    fields = {
        "n_input_tokens": "n_input_tokens",
        "n_output_tokens": "n_output_tokens",
        "n_cache_tokens": "n_cache_tokens",
        "cost_usd": "cost_usd",
    }
    for out_key, attr in fields.items():
        value = getattr(agent_result, attr, None)
        if value:
            usage[out_key] = float(value)
    tok = usage.get("n_input_tokens", 0) + usage.get("n_output_tokens", 0)
    if tok:
        usage["n_total_tokens"] = tok
    return usage


class LocalExecutor:
    """Runs episodes on this machine — the task's real judge, no Docker.

    The contract is identical to the container run: the same
    ``judge_server.py`` that runs as a sidecar in containers is started as a
    local process, your command gets ``$JUDGE_URL`` (and ``$BUDGET_SEC``)
    and submits solutions to it, and the final result is the judge's
    verdict. Being killed at the deadline is a normal ending.

    Fast and dependency-free — the development loop. Local rows carry a
    ``local://`` uri because the judge ran on a machine the agent also
    controls; report container numbers. Works for any task following the
    template layout (``environment/judge_server.py`` + ``score.py``);
    image-based tasks (EdgeBench, FrontierCS) need containers.
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else None
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)

    async def execute(self, spec: EpisodeSpec) -> EpisodeResult:
        task_dir = Path(spec.task)
        judge_dir = task_dir / "environment"
        if not (
            (judge_dir / "judge_server.py").is_file()
            and (judge_dir / "score.py").is_file()
        ):
            return EpisodeResult(
                rewards={},
                error=f"{spec.task} does not follow the template layout "
                "(environment/judge_server.py + score.py) — run it in containers",
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
        port = _free_port()
        judge = subprocess.Popen(
            [sys.executable, str(judge_dir / "judge_server.py")],
            env={
                **os.environ,
                "PORT": str(port),
                "JUDGE_DIR": str(judge_dir),
                "DATA_DIR": str(workdir / "judge_data"),
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        judge_url = f"http://127.0.0.1:{port}"
        try:
            await asyncio.to_thread(_wait_healthy, judge_url)

            error = None
            try:
                proc = await asyncio.to_thread(
                    subprocess.run,
                    command,
                    shell=True,
                    env={
                        **os.environ,
                        "JUDGE_URL": judge_url,
                        "BUDGET_SEC": str(budget),
                        # Budget signals (TIDE_MAX_TOKENS, ...) the command may pace on.
                        **spec.agent.get("env", {}),
                    },
                    timeout=float(budget),
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    error = (
                        f"agent command exited {proc.returncode}: {proc.stderr[-500:]}"
                    )
            except subprocess.TimeoutExpired:
                pass  # budget spent — a normal ending

            final = await asyncio.to_thread(_get_json, f"{judge_url}/final")
        finally:
            judge.kill()

        submissions = final.get("submissions", [])
        with (workdir / "submissions.jsonl").open("w") as f:
            for entry in submissions:
                f.write(json.dumps({"t": entry["t"], "score": entry["score"]}) + "\n")
        return EpisodeResult(
            rewards={"reward": float(final["reward"])},
            uri=f"local://{workdir}",
            trace=tuple(TracePoint(t=e["t"], score=e["score"]) for e in submissions),
            error=error,
            usage={"n_submissions": float(len(submissions))},
        )


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_healthy(judge_url: str, timeout_sec: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_sec
    while True:
        try:
            urllib.request.urlopen(f"{judge_url}/health", timeout=2)
            return
        except Exception as e:
            if time.monotonic() > deadline:
                raise RuntimeError(f"judge at {judge_url} never became healthy") from e
            time.sleep(0.05)


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read())


class FakeExecutor:
    """Deterministic executor for tests and demos.

    ``score`` maps a spec to rewards; the default scores by a stable hash of
    the task name so demos produce varied but reproducible numbers. ``trace``
    optionally fabricates a submission log per spec.
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
