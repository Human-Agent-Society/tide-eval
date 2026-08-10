"""The task-suite contract, enforced for every first-party task.

Each task under tasks/ that ships a ``tests/vectors.json`` gets, automatically:

- an **oracle check** — the known-good artifact scores its expected reward
  (exact, approx, or a [min, max] range);
- **cheat checks** — every cheat artifact scores exactly 0 with a reason;
- a **stock-Harbor check** — its ``task.toml`` validates under Harbor's
  ``TaskConfig`` (skipped when harbor isn't installed).

Adding a task therefore means adding a folder; the suite picks it up with no
test code written. This is the anti-hack wall as a standing contract, not a
per-task effort.
"""

import importlib.util
import json
from pathlib import Path

import pytest

TASKS_ROOT = Path(__file__).parent.parent / "tasks"
# The template ships as a complete working task and is held to the same
# contract, so copying it always starts from green.
VECTOR_TASKS = sorted(
    p.parent.parent for p in TASKS_ROOT.glob("*/*/tests/vectors.json")
) + [TASKS_ROOT / "_template"]
ALL_TASKS = sorted(
    p.parent
    for p in TASKS_ROOT.glob("*/*/task.toml")
    if not any(part.startswith("_") for part in p.parts)
)


def _load_grader(task_dir: Path):
    spec = importlib.util.spec_from_file_location(
        f"grade_{task_dir.name}", task_dir / "tests" / "grade.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_artifact(tmp_path: Path, payload) -> Path:
    artifact = tmp_path / "solution.json"
    artifact.write_text(json.dumps(payload))
    return artifact


def _vectors(task_dir: Path) -> dict:
    return json.loads((task_dir / "tests" / "vectors.json").read_text())


@pytest.mark.parametrize("task_dir", VECTOR_TASKS, ids=lambda p: p.name)
def test_oracle_scores_expected(task_dir, tmp_path):
    grader = _load_grader(task_dir)
    oracle = _vectors(task_dir)["oracle"]
    result = grader.grade(_write_artifact(tmp_path, oracle["artifact"]))
    reward = result["reward"]
    if "reward" in oracle:
        assert reward == pytest.approx(
            oracle["reward"], abs=oracle.get("tolerance", 1e-9)
        ), result
    else:
        assert oracle["reward_min"] <= reward <= oracle["reward_max"], result


@pytest.mark.parametrize("task_dir", VECTOR_TASKS, ids=lambda p: p.name)
def test_cheats_score_zero(task_dir, tmp_path):
    grader = _load_grader(task_dir)
    for cheat in _vectors(task_dir)["cheats"]:
        result = grader.grade(_write_artifact(tmp_path, cheat["artifact"]))
        assert result["reward"] == 0.0, f"cheat {cheat['name']!r} scored: {result}"
        assert result.get("reason"), f"cheat {cheat['name']!r} gave no reason"


@pytest.mark.parametrize("task_dir", VECTOR_TASKS, ids=lambda p: p.name)
def test_missing_artifact_scores_zero(task_dir):
    grader = _load_grader(task_dir)
    assert grader.grade(None)["reward"] == 0.0


@pytest.mark.parametrize("task_dir", VECTOR_TASKS, ids=lambda p: p.name)
def test_task_is_stock_harbor(task_dir):
    pytest.importorskip("harbor")
    import tomllib

    from harbor.models.task.config import TaskConfig

    TaskConfig.model_validate(tomllib.loads((task_dir / "task.toml").read_text()))
    for required in (
        "instruction.md",
        "environment/Dockerfile",
        "tests/test.sh",
        "solution/solve.sh",
    ):
        assert (task_dir / required).exists(), f"{task_dir.name} missing {required}"


@pytest.mark.parametrize(
    "task_dir", ALL_TASKS, ids=lambda p: f"{p.parent.name}/{p.name}"
)
def test_every_committed_task_validates(task_dir):
    """Every task in the catalog — first-party AND synced external — is a
    valid stock Harbor task."""
    pytest.importorskip("harbor")
    import tomllib

    from harbor.models.task.config import TaskConfig

    TaskConfig.model_validate(tomllib.loads((task_dir / "task.toml").read_text()))
    assert (task_dir / "instruction.md").exists()
