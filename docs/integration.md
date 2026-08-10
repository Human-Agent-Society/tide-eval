# Evaluating your agent, harness, or method

An "agent" in tide is anything Harbor can run against the task container.
Three integration levels, cheapest first. In every case the task, the
trust wall, the budget, and the results store are identical — so numbers
stay comparable across methods, models, and time.

## Level 1 — a supported harness (zero code)

Harbor ships adapters for the mainstream agent CLIs — `claude-code`,
`codex`, `aider`, `cursor-cli`, `terminus-2`, and more — plus two
reference agents you should always keep in rotation: `oracle` (runs the
task's own `solution/`, proving the pipeline) and `nop` (does nothing,
catching score leakage). Name one, pick a model, go:

```bash
tide run autoresearch --agent claude-code --model anthropic/claude-opus-5
tide run edgebench/ann_vector_search_qps --agent codex --budget 2   # hours
```

`--budget` sets the agent timeout and stamps a `budget` tag, so
budget-scaling curves come out of the store for free. Extra `AgentConfig`
fields pass through with `--agent-arg key=value`.

## Level 2 — your own harness (one class)

If your harness has its own loop, tools, and model orchestration,
implement Harbor's `BaseAgent`:

```python
from harbor.agents.base import BaseAgent


class MyAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "my-agent"

    def version(self) -> str | None:
        return "0.1"

    async def setup(self, environment) -> None:
        # install your harness into the container
        await environment.exec(command="pip install my-harness")

    async def run(self, instruction, environment, context) -> None:
        # drive your loop: your models, your tools, your orchestration.
        # `instruction` is the task's instruction.md; `environment.exec`
        # runs commands inside the (untrusted) task container.
        ...
```

Reference it by import path — the agent dict passes verbatim to Harbor's
`AgentConfig`:

```python
from tide import Lab

lab = Lab("runs/my-harness")
row = await lab.run(
    "tasks/autoresearch/circle-packing",
    agent={"import_path": "my_pkg.my_agent:MyAgent", "model_name": "..."},
    tags={"harness": "my-harness", "budget": 1},
)
```

Your harness keeps everything it owns; tide owns the container, the
budget, the wall, and the store.

## Level 3 — your method isn't an "agent" at all

An evolutionary search, a solver portfolio, a bare sampling loop —
anything qualifies, because the task contract is deliberately tiny:

1. **Keep your best solution written to the declared artifact path**
   (e.g. `/app/best/solution.json`), atomically (temp file + rename), at
   all times — this is what gets graded, whenever the budget ends.
2. Optionally, **append self-scores to `score_log.jsonl`**
   (`{"t": <sec>, "score": <x>}` per line) — this becomes your method's
   progress curve in the store.

A `BaseAgent.run()` that installs and launches your optimizer inside the
container is a complete integration. The public scorer baked into every
task image (`environment/scorer.py`) gives your method its inner-loop
feedback signal for free — call it as often as you like; it is
deliberately unisolated because nothing inside the container is believed.

### The first-party task contract, at a glance

Every path below is identical across all six
[first-party tasks](../tasks/autoresearch), so one integration covers the
whole suite:

| What | Where |
|---|---|
| the problem statement | `instruction.md` — passed to your agent's `run()` as `instruction` |
| public scorer | `python /app/scorer.py /app/best/solution.json` → prints a bare float |
| gradeable artifact | `/app/best/solution.json` — atomic writes (temp file + rename) |
| self-eval log | `/app/best/score_log.jsonl` — `{"t": <sec>, "score": <x>}` per line |
| what the verifier sees | **only** the files declared in `task.toml`'s `artifacts` |

External catalogs (EdgeBench, FrontierCS, AlgoTune) keep their upstream
interfaces — each task's `instruction.md` states them, and the artifact
list is always in its `task.toml`.

### Worked example: plugging in OpenEvolve

An [OpenEvolve](https://github.com/codelion/openevolve)-style evolutionary
search needs a seed program and an `evaluate(program_path) -> metrics`
function. The uniform contract makes that evaluator one shim, valid for
all six tasks — run the candidate, score its output with the task's public
scorer, and keep the gradeable artifact current:

```python
# evaluator.py — uploaded into the container next to your seed program.
import json
import pathlib
import subprocess
import time

BEST = pathlib.Path("/app/best/solution.json")
LOG = pathlib.Path("/app/best/score_log.jsonl")
T0 = time.monotonic()
best = 0.0


def evaluate(program_path: str) -> dict:
    global best
    run = subprocess.run(["python", program_path], capture_output=True, timeout=120)
    candidate = pathlib.Path("/tmp/candidate.json")
    candidate.write_bytes(run.stdout)  # convention: candidate prints its solution
    scored = subprocess.run(
        ["python", "/app/scorer.py", str(candidate)],
        capture_output=True,
        text=True,
    )
    score = float(scored.stdout.strip() or 0.0)
    if score > best:  # the artifact must always hold the best-so-far
        best = score
        tmp = BEST.with_suffix(".tmp")
        tmp.write_bytes(candidate.read_bytes())
        tmp.rename(BEST)
        with LOG.open("a") as f:
            f.write(json.dumps({"t": time.monotonic() - T0, "score": score}) + "\n")
    return {"combined_score": score}
```

The agent class installs OpenEvolve in the container, ships the shim and
seed, forwards the LLM key from the host environment (the same pattern
Harbor's built-in agents use), and launches the controller — the budget
kills it whenever time is up, and `/app/best/` stays gradeable throughout:

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
        await environment.upload_dir(
            "./openevolve_setup", "/opt/oe"
        )  # seed + evaluator.py

    async def run(self, instruction, environment, context) -> None:
        await environment.exec(
            command="cd /opt/oe && openevolve-run seed.py evaluator.py --iterations 100000",
            env={"OPENAI_API_KEY": os.environ["OPENAI_API_KEY"]},
        )
```

```python
row = await lab.run(
    "tasks/autoresearch/circle-packing",
    agent={"import_path": "my_pkg.openevolve_agent:OpenEvolveAgent"},
    tags={"harness": "openevolve", "budget": 1},
)
```

Sanity-check any new integration the cheap way first: `--agent oracle`
proves the task pipeline, `--agent nop` proves your score isn't leaking,
and the fake executor (`tide run ... --fake`) exercises your sweep script
with no containers at all.

## The one thing you cannot bring

Your own grader. Trusted scores come from the task's verifier, running in
its own container on declared artifacts only — or they don't exist. If
your method needs a different scoring rule, that's a new task
(five-minute template: [`tasks/_template`](../tasks/_template)), not a
new grader for an existing one.

## Comparing methods fairly

- Run every method at the **same budget tag** on the same tasks; compare
  `episode.reward` (trusted) first, anytime/AUC (claimed) second — and say
  which is which.
- `oracle` and `nop` bracket the score range: a method below nop leaks; a
  method above oracle beat the reference solution.
- Pin identity into tags (`harness`, `model`, `budget`, `attempt`) —
  every comparison is then a pivot over `lab.df()`, and every number's
  `uri` points at the trial directory that can be audited.
