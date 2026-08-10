"""The AlgoTune converter, end to end: convert a fixture task shaped like
the official adapter's output, then run it through the local judge —
session timing, final timing, and upstream's mercy rules included."""

import json
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tasks" / "algotune"))
from fetch import convert  # noqa: E402

EVALUATOR = """
class Task:
    def generate_problem(self, n, random_seed=1):
        return {"n": n + random_seed}

    def solve(self, problem):
        return sum(i * i for i in range(2000 + problem["n"]))

    def is_solution(self, problem, solution):
        return solution == self.solve(problem)
"""

SOLVER_OK = """
class Solver:
    def solve(self, problem):
        return sum(i * i for i in range(2000 + problem["n"]))
"""

TASK_TOML = """
schema_version = "1.0"

[task]
name = "algotune/algotune__fixture"

[metadata]
source = "algotune"
algotune_problem_size = 10

[verifier]
network_mode = "public"
timeout_sec = 3600.0

[agent]
network_mode = "public"
timeout_sec = 3600.0

[environment]
build_timeout_sec = 1800.0
cpus = 8
memory_mb = 16384
"""

SOLVE_SH = """#!/bin/bash
set -euo pipefail
cat > /app/solver.py <<'EOF'
class Solver:
    def solve(self, problem):
        return sum(i * i for i in range(2000 + problem["n"]))
EOF
echo "Solver artifacts installed."
"""


@pytest.fixture()
def adapter_output(tmp_path) -> Path:
    src = tmp_path / "algotune__fixture"
    (src / "tests").mkdir(parents=True)
    (src / "environment").mkdir()
    (src / "solution").mkdir()
    (src / "tests" / "evaluator.py").write_text(textwrap.dedent(EVALUATOR))
    (src / "instruction.md").write_text("# Fixture task\n\nSpeed up the sum.\n")
    (src / "task.toml").write_text(TASK_TOML.strip() + "\n")
    (src / "environment" / "Dockerfile").write_text(
        "FROM python:3.12-slim\nWORKDIR /app\n"
    )
    (src / "solution" / "solve.sh").write_text(SOLVE_SH)
    return src


def test_converted_layout_and_config(adapter_output, tmp_path):
    task = convert(adapter_output, out_root=tmp_path / "out")
    for required in (
        "environment/judge_server.py",
        "environment/score.py",
        "environment/final.py",
        "environment/algotune_timing.py",
        "environment/evaluator.py",
        "environment/params.json",
        "environment/Dockerfile.judge",
        "environment/docker-compose.yaml",
        "tests/grade.py",
        "tests/test.sh",
        "solution/solve.sh",
    ):
        assert (task / required).is_file(), required
    assert json.loads((task / "environment" / "params.json").read_text()) == {
        "problem_size": 10
    }
    solve = (task / "solution" / "solve.sh").read_text()
    assert "/tmp/solver.py" in solve and "JUDGE_URL" in solve

    harbor = pytest.importorskip("harbor")  # noqa: F841
    import tomllib

    from harbor.models.task.config import TaskConfig

    config = TaskConfig.model_validate(tomllib.loads((task / "task.toml").read_text()))
    assert config.environment.network_mode.value == "allowlist"


async def test_converted_task_through_the_local_judge(adapter_output, tmp_path):
    from tide import Lab, LocalExecutor

    task = convert(adapter_output, out_root=tmp_path / "out")
    solver = tmp_path / "solver.py"
    solver.write_text(textwrap.dedent(SOLVER_OK))
    submit = (
        f'{sys.executable} -c "import os,urllib.request;'
        f"urllib.request.urlopen(urllib.request.Request("
        f"os.environ['JUDGE_URL']+'/submit',"
        f"data=open('{solver}','rb').read()),timeout=120)\""
    )
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))
    row = await lab.run(str(task), {"command": submit, "override_timeout_sec": 300})

    # A solver identical to the baseline lands at the 1.0 mercy floor (or a
    # hair above, from timing noise) — never below, never a large speedup.
    assert 1.0 <= row.rewards["reward"] < 1.5
    assert len(lab.df("trace")) == 1
