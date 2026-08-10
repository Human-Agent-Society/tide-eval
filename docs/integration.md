# Evaluating your agent, harness, or method

An "agent" is anything Harbor can run against the task container. Same
tasks, same wall, same store — numbers stay comparable across methods.

## Level 1 — a supported harness (zero code)

`claude-code`, `codex`, `aider`, `cursor-cli`, `terminus-2`, … plus
`oracle` (runs the task's solution — proves the pipeline) and `nop` (does
nothing — catches leakage):

```bash
tide run autoresearch --agent claude-code --model anthropic/claude-opus-5
tide run edgebench/ann_vector_search_qps --agent codex --budget 2   # hours
```

`--budget` sets the timeout and a `budget` tag; extra `AgentConfig` fields
pass via `--agent-arg key=value`.

## Level 2 — your own harness (one class)

Implement Harbor's `BaseAgent`, reference it by import path:

```python
from harbor.agents.base import BaseAgent


class MyAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "my-agent"

    def version(self) -> str | None:
        return "0.1"

    async def setup(self, environment) -> None:
        await environment.exec(command="pip install my-harness")

    async def run(
        self, instruction, environment, context
    ) -> None: ...  # your loop; `instruction` is the task's instruction.md
```

```python
row = await lab.run(
    "tasks/autoresearch/circle-packing",
    agent={"import_path": "my_pkg.my_agent:MyAgent", "model_name": "..."},
    tags={"harness": "my-harness", "budget": 1},
)
```

Runnable version: [`examples/minimal_harness.py`](../examples/minimal_harness.py)
— a ~30-line adapter + a random-search loop, no LLM, no keys.

**Your code runs on the host**; the container is reached via
`environment.exec(command=...)` / `upload_dir` / `download_file`. Two
placements, both fine (only declared artifacts reach the verifier):

- **Host-side loop** — your method keeps its own GPUs / inference server /
  orchestrator, and uses the container only to execute and score
  candidates via `exec`. The fit for external learners (TTT-style training
  loops) and host-side multi-agent systems (CORAL-style).
- **In-container** — upload your method and launch it (OpenEvolve example
  below). LLM calls from inside need the task's network policy opened:
  an `allowlist` on the `[agent]` phase, keys via `exec(..., env={...})` —
  see [network policy](components/tasks.md#network-policy).

For learning methods: the public scorer's per-candidate numbers are your
**training signal** (free, dense, untrusted); the verifier's episode score
is the **eval number**. Your method never sees the verifier.

## Level 3 — your method isn't an "agent" at all

Evolutionary search, solver, sampling loop — the task contract is two rules:

1. keep your best solution at the declared artifact path, atomically
   (temp file + rename) — that's what gets graded when the budget ends;
2. optionally append `{"t": <sec>, "score": <x>}` lines to
   `score_log.jsonl` — that becomes your progress curve in the store.

The contract is identical across all six first-party tasks:

| What | Where |
|---|---|
| problem statement | `instruction.md` → your agent's `instruction` |
| public scorer | `python /app/scorer.py /app/best/solution.json` → prints a float |
| gradeable artifact | `/app/best/solution.json` |
| self-eval log | `/app/best/score_log.jsonl` |
| verifier sees | **only** the `artifacts` declared in `task.toml` |

### Worked example: OpenEvolve

One evaluator shim covers all six tasks — score the candidate with the
task's scorer, keep the artifact current:

```python
# evaluator.py — uploaded into the container next to your seed program.
import json, pathlib, subprocess, time

BEST = pathlib.Path("/app/best/solution.json")
LOG = pathlib.Path("/app/best/score_log.jsonl")
T0, best = time.monotonic(), 0.0


def evaluate(program_path: str) -> dict:
    global best
    run = subprocess.run(["python", program_path], capture_output=True, timeout=120)
    cand = pathlib.Path("/tmp/candidate.json")
    cand.write_bytes(run.stdout)  # candidate prints its solution
    out = subprocess.run(
        ["python", "/app/scorer.py", str(cand)], capture_output=True, text=True
    )
    score = float(out.stdout.strip() or 0.0)
    if score > best:
        best = score
        tmp = BEST.with_suffix(".tmp")
        tmp.write_bytes(cand.read_bytes())
        tmp.rename(BEST)
        with LOG.open("a") as f:
            f.write(json.dumps({"t": time.monotonic() - T0, "score": score}) + "\n")
    return {"combined_score": score}
```

```python
import os

from harbor.agents.base import BaseAgent


class OpenEvolveAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "openevolve"

    def version(self) -> str | None:
        return None

    async def setup(self, environment) -> None:
        await environment.exec(command="pip install openevolve")
        await environment.upload_dir("./oe_setup", "/opt/oe")  # seed + evaluator.py

    async def run(self, instruction, environment, context) -> None:
        await environment.exec(
            command="cd /opt/oe && openevolve-run seed.py evaluator.py --iterations 100000",
            env={"OPENAI_API_KEY": os.environ["OPENAI_API_KEY"]},
        )
```

## Rules of the game

- **You cannot bring your own grader.** Trusted scores come from the task's
  verifier or they don't exist. Different scoring rule = a new task
  ([`tasks/_template`](../tasks/_template)), not a new grader.
- **Compare at the same `budget` tag**; trusted `reward` first, claimed
  anytime/AUC second. `oracle` and `nop` bracket the range.
- **Sanity-check cheaply**: `--agent oracle` proves the task, `--agent nop`
  proves no leakage, `--fake` exercises your sweep script with no containers.
