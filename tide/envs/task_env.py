"""TaskEnv: an autoresearch task as a Gym-style environment.

The observation is the task (instruction + data files). Each ``step`` takes
a candidate solution and scores it with the task's **real grader**, run
locally as plain Python — no containers — so a propose→score loop iterates
in milliseconds. The env tracks the best solution so far, which makes every
run an anytime curve for free.

Two scoring channels, mirroring the task protocol:

- ``step`` uses the task's *step scorer* — for most tasks this IS the trusted
  grader (nothing is hidden); tasks with held-out information (symbolic
  regression) score steps on the public data only;
- ``final()`` always applies the trusted grader to the best solution — for
  held-out tasks this is the number that would come out of the containerized
  pipeline, and the honest one to report.

For evaluating a full agent (its own tooling, a container, a wall clock),
use the containerized pipeline instead: ``tide run <task> --agent <name>``.
Same tasks, same graders, one measurement story.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tide.envs.core import Observation, StepResult

StepScorer = Callable[[Path, Any], dict]  # (task_dir, action) -> grade-style dict


def load_grader(task_dir: Path):
    spec = importlib.util.spec_from_file_location(
        f"tide_grade_{task_dir.name}", task_dir / "tests" / "grade.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def trusted_grade(task_dir: Path, action: Any) -> dict:
    """Run the task's real grader on a candidate solution, locally."""
    grader = load_grader(task_dir)
    with tempfile.TemporaryDirectory() as tmp:
        artifact = Path(tmp) / "solution.json"
        artifact.write_text(json.dumps(action))
        return grader.grade(artifact)


class TaskEnv:
    def __init__(
        self,
        task_dir: str | Path,
        *,
        max_steps: int | None = None,
        step_scorer: StepScorer | None = None,
    ):
        self.task_dir = Path(task_dir)
        if not (self.task_dir / "task.toml").is_file():
            raise FileNotFoundError(f"not a task dir: {self.task_dir}")
        self.max_steps = max_steps
        self._step_scorer = step_scorer or trusted_grade
        self._steps = 0
        self.best_action: Any = None
        self.best_reward = float("-inf")

    # ------------------------------------------------------------------ api

    def reset(self, *, seed: int | None = None) -> tuple[Observation, dict]:
        self._steps = 0
        self.best_action, self.best_reward = None, float("-inf")
        env_dir = self.task_dir / "environment"
        files = {
            p.name: p.read_text()
            for p in sorted(env_dir.iterdir())
            if p.suffix in (".json", ".txt") and p.is_file()
        }
        obs: Observation = {
            "instruction": (self.task_dir / "instruction.md").read_text(),
            "files": files,
        }
        return obs, {"task": self.task_dir.name}

    def step(self, action: Any) -> StepResult:
        self._steps += 1
        result = dict(self._step_scorer(self.task_dir, action))
        reward = float(result.pop("reward", 0.0))
        if reward > self.best_reward:
            self.best_reward, self.best_action = reward, action
        truncated = self.max_steps is not None and self._steps >= self.max_steps
        info = {**result, "step": self._steps, "best_reward": self.best_reward}
        # Open-ended optimization never "succeeds" — it runs until the budget
        # (max_steps) truncates it or the caller stops.
        return None, reward, False, truncated, info

    def final(self) -> dict:
        """The trusted grade of the best solution seen — the number to report."""
        if self.best_action is None:
            return {"reward": 0.0, "reason": "no solution submitted"}
        return trusted_grade(self.task_dir, self.best_action)

    def close(self) -> None:
        pass


# ----------------------------------------------------- special step scorers


def symbolic_regression_train_scorer(task_dir: Path, action: Any) -> dict:
    """Step scorer for symbolic-regression: identical grading logic, but on
    the TRAIN points the agent is allowed to see. ``final()`` still grades on
    the held-out points — the anti-overfitting wall survives gym mode."""
    grader = load_grader(task_dir)
    import math

    try:
        expr = action["expr"]
        if not isinstance(expr, str) or len(expr) > grader.MAX_EXPR_LEN:
            raise TypeError("expr must be a string within the length limit")
        points = json.loads((task_dir / "environment" / "train.json").read_text())[
            "points"
        ]
        errors = []
        for x, y in points:
            prediction = grader.evaluate(expr, x)
            if not math.isfinite(prediction):
                return {"reward": 0.0, "reason": f"non-finite prediction at x={x}"}
            errors.append((prediction - y) ** 2)
        rmse = math.sqrt(sum(errors) / len(errors))
        return {"reward": 1.0 / (1.0 + rmse), "rmse_train": rmse}
    except (
        KeyError,
        TypeError,
        ValueError,
        SyntaxError,
        ZeroDivisionError,
        OverflowError,
    ) as e:
        return {"reward": 0.0, "reason": f"invalid expr: {e}"}
