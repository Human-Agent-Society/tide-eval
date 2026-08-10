#!/usr/bin/env python3
"""Convert official-adapter AlgoTune tasks to tide's judge protocol.

The official Harbor adapter
(https://github.com/laude-institute/harbor/tree/main/adapters/algotune)
turns AlgoTune's 154 tasks into Harbor task dirs where the agent writes
``/app/solver.py`` and a verifier times it once, at the end, against the
reference implementation (100 instances x 10 repeats, interleaved).

This script re-shapes such a task dir into the judge protocol:

- the judge's **session score** runs a light version of the same timing
  protocol (5 instances x 3 repeats) on every submission — cheap,
  noisier feedback for the agent's loop;
- the judge's **final score** runs the official protocol (100 x 10) once,
  on the best submission — that is the number that counts;
- the same mercy rules as upstream: invalid or slower-than-baseline
  scores 1.0; a submission that is not loadable Python with a ``Solver``
  class scores 0.0 with a reason.

Usage:

    # 1. generate tasks with the official adapter (their README), then:
    python tasks/algotune/fetch.py <adapter-output-task-dir> [more dirs...]

Converted tasks are written next to this script, one folder per task.
"""

import json
import shutil
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE_ENV = HERE.parent / "_template" / "environment"
TEMPLATE_TESTS = HERE.parent / "_template" / "tests"

TIMING = '''"""Shared AlgoTune timing core — upstream's interleaved protocol."""

import importlib.util
import json
import time
from pathlib import Path

import evaluator

PARAMS = json.loads((Path(__file__).parent / "params.json").read_text())
task = evaluator.Task()


def _load_solver(path: Path):
    spec = importlib.util.spec_from_file_location("submitted_solver", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Solver()


def _interleaved(solve, baseline, problem, repeats):
    try:
        _ = baseline(problem)
        warmup = solve(problem)
        if not task.is_solution(problem, warmup):
            return -1.0, -1.0
    except Exception:
        return -1.0, -1.0
    solver_times, baseline_times = [], []
    for _ in range(repeats):
        try:
            t0 = time.perf_counter_ns()
            baseline(problem)
            baseline_times.append(time.perf_counter_ns() - t0)
            t0 = time.perf_counter_ns()
            solve(problem)
            solver_times.append(time.perf_counter_ns() - t0)
        except Exception:
            return -1.0, -1.0
    return min(solver_times), min(baseline_times)


def evaluate(artifact: Path, instances: int, repeats: int) -> dict:
    """Upstream scoring: speedup = total baseline time / total solver time,
    with a mercy floor of 1.0 for valid-but-slower or invalid solutions."""
    solver_path = Path(artifact).with_suffix(".py")
    solver_path.write_bytes(Path(artifact).read_bytes())
    try:
        solver = _load_solver(solver_path)
    except Exception as e:
        return {"reward": 0.0, "reason": f"could not load a Solver class: {e!r}"}

    total_solver = total_baseline = 0.0
    for i in range(instances):
        problem = task.generate_problem(n=PARAMS["problem_size"], random_seed=i)
        t_solver, t_baseline = _interleaved(
            solver.solve, task.solve, problem, repeats
        )
        if t_solver < 0:
            return {"reward": 1.0, "reason": "invalid solution — mercy score"}
        total_solver += t_solver
        total_baseline += t_baseline

    raw = total_baseline / total_solver if total_solver > 0 else 0.0
    if raw < 1.0:
        return {"reward": 1.0, "reason": f"slower than baseline ({raw:.2f}x) — mercy score"}
    return {"reward": raw, "reason": f"speedup {raw:.2f}x over {instances} instances"}
'''

SCORE = '''"""Session score: the light timing protocol, run on every submission."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from algotune_timing import evaluate  # noqa: E402


def grade(artifact: Path | None) -> dict:
    if artifact is None or not Path(artifact).exists():
        return {"reward": 0.0, "reason": "no solver submitted"}
    return evaluate(Path(artifact), instances=5, repeats=3)
'''

FINAL = '''"""Final score: the official AlgoTune protocol, run once on the best."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from algotune_timing import evaluate  # noqa: E402


def grade(artifact: Path | None) -> dict:
    if artifact is None or not Path(artifact).exists():
        return {"reward": 0.0, "reason": "no solver submitted"}
    return evaluate(Path(artifact), instances=100, repeats=10)
'''

PROTOCOL = """

## How you are scored

Develop and time your solver however you like inside your container (all
the libraries are installed), then submit the **source of your solver.py**
to the judge:

```bash
curl -s -X POST --data-binary @solver.py "$JUDGE_URL/submit"
```

Each submission is timed with a light version of the official protocol
(5 instances x 3 repeats) — quick, slightly noisy feedback. Your **best
submission is re-timed once at the end with the official protocol**
(100 instances x 10 repeats), and that number is your score. You have a
limited number of submissions (`GET $JUDGE_URL/status`); an invalid or
slower-than-baseline solver scores 1.0, matching upstream AlgoTune.
"""

SOLVE_SUBMIT = """
python3 - <<'SUBMIT'
import json, os, urllib.request
req = urllib.request.Request(
    os.environ["JUDGE_URL"] + "/submit", data=open("/tmp/solver.py", "rb").read()
)
print(json.loads(urllib.request.urlopen(req, timeout=300).read()))
SUBMIT
"""


def convert(src: Path, out_root: Path = HERE) -> Path:
    name = src.name
    dst = out_root / name
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "environment").mkdir(parents=True)
    (dst / "tests").mkdir()
    (dst / "solution").mkdir()

    # --- judge side: their Task class + our protocol files ---
    shutil.copy(src / "tests" / "evaluator.py", dst / "environment" / "evaluator.py")
    (dst / "environment" / "algotune_timing.py").write_text(TIMING)
    (dst / "environment" / "score.py").write_text(SCORE)
    (dst / "environment" / "final.py").write_text(FINAL)
    shutil.copy(
        TEMPLATE_ENV / "judge_server.py", dst / "environment" / "judge_server.py"
    )
    (dst / "environment" / "judge_config.json").write_text(
        '{"max_submissions": 100, "min_interval_sec": 0}\n'
    )

    config = tomllib.loads((src / "task.toml").read_text())
    size = config.get("metadata", {}).get("algotune_problem_size", 100)
    (dst / "environment" / "params.json").write_text(
        json.dumps({"problem_size": int(size)}) + "\n"
    )

    # --- images: agent keeps their full stack; judge gets it too ---
    agent_docker = (src / "environment" / "Dockerfile").read_text()
    (dst / "environment" / "Dockerfile").write_text(agent_docker)
    judge_docker = agent_docker.rstrip() + (
        "\n\nCOPY judge_server.py score.py final.py algotune_timing.py"
        " evaluator.py judge_config.json params.json /judge/\n"
        'CMD ["python3", "/judge/judge_server.py"]\n'
    )
    (dst / "environment" / "Dockerfile.judge").write_text(judge_docker)
    compose = (TEMPLATE_ENV / "docker-compose.yaml").read_text()
    (dst / "environment" / "docker-compose.yaml").write_text(compose)

    # --- verifier: the generic finalize-from-judge pair ---
    shutil.copy(TEMPLATE_TESTS / "grade.py", dst / "tests" / "grade.py")
    shutil.copy(TEMPLATE_TESTS / "test.sh", dst / "tests" / "test.sh")

    # --- instruction: theirs + the submission protocol ---
    instruction = (src / "instruction.md").read_text().rstrip()
    (dst / "instruction.md").write_text(instruction + PROTOCOL)

    # --- reference solution: write their solver, submit it once ---
    solve = (src / "solution" / "solve.sh").read_text()
    assert "/app/solver.py" in solve, f"{name}: unexpected solve.sh shape"
    solve = solve.replace("/app/solver.py", "/tmp/solver.py")
    solve = solve.replace('echo "Solver artifacts installed."', "")
    (dst / "solution" / "solve.sh").write_text(solve.rstrip() + "\n" + SOLVE_SUBMIT)

    # --- task.toml: no artifacts, judge-only environment network ---
    toml_text = (src / "task.toml").read_text()
    toml_text = toml_text.replace(
        'schema_version = "1.0"', 'schema_version = "1.0"\n\nartifacts = []'
    )
    toml_text = toml_text.rstrip() + (
        '\nnetwork_mode = "allowlist"\nallowed_hosts = ["judge"]\n'
    )
    (dst / "task.toml").write_text(toml_text)
    return dst


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for arg in sys.argv[1:]:
        out = convert(Path(arg))
        print(f"converted: {out}")
