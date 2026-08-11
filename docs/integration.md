# Evaluating your agent, harness, or method

An "agent" is anything Harbor can run against the task container. Three
integration levels follow, cheapest first. Whichever you pick, the task,
the judge, and the results store are identical, so numbers stay comparable
across methods.

## The contract, first

Every task gives your agent two environment variables and one protocol:

| | |
|---|---|
| `$JUDGE_URL` | the judge's HTTP address |
| `$BUDGET_SEC` | your time budget (local runs; containers use the task timeout) |
| `POST $JUDGE_URL/submit` | body = your solution file → `{"score", "best", "remaining", ...}`; over budget → 429 |
| `GET $JUDGE_URL/status` | submissions used / remaining, best so far |

Your final score is your best submission (re-scored by a final judge with
hidden tests, if the task has one). Everything else — how you search, what
you evaluate locally, whether you build your own scorer — is your
business; tide places no constraints on the agent's side.

## Level 1 — a supported harness (zero code)

`claude-code`, `codex`, `aider`, `cursor-cli`, `terminus-2`, … plus
`oracle` (submits the task's reference solution — proves the pipeline) and
`nop` (does nothing — catches leakage):

```bash
tide run autoresearch --agent claude-code --model anthropic/claude-opus-5
tide run autoresearch/tsp-tour --agent codex --budget 2   # hours
```

The instruction tells the harness the submission protocol; `--budget` sets
the timeout and a `budget` tag. Extra `AgentConfig` fields pass via
`--agent-arg key=value`.

## Level 2 — your own harness (one class)

Implement Harbor's `BaseAgent`, reference it by import path. Your code
runs on the host; the container (where `$JUDGE_URL` lives) is reached via
`environment.exec` / `upload_dir` / `download_file`:

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
    ) -> None: ...  # your loop; submit from inside via $JUDGE_URL
```

```python
row = await lab.run(
    "tasks/autoresearch/circle-packing",
    agent={"import_path": "my_pkg.my_agent:MyAgent", "model_name": "..."},
    tags={"harness": "my-harness", "budget": 1},
)
```

Runnable version: [`examples/minimal_harness.py`](../examples/minimal_harness.py)
— a ~25-line adapter around a random-search loop, no LLM, no keys.

Two placements for your method, both fine:

- **Host-side loop** — your method keeps its own GPUs / inference server /
  orchestrator and submits through the container
  (`environment.exec(command="curl ... $JUDGE_URL/submit")`). The fit for
  external learners (TTT-style training loops) and host-side multi-agent
  systems (CORAL-style).
- **In-container** — upload your method and launch it; it talks to the
  judge directly. LLM calls from inside need the task's network policy
  opened: add your API host to the `[agent]` phase allowlist — see
  [network policy](components/tasks.md#network-policy).

## Level 3 — your method isn't an "agent" at all

An evolutionary search, a solver portfolio, a bare sampling loop — the
whole integration is: read `$JUDGE_URL`, POST candidates worth scoring,
stop at 429. The minimal version is ~20 lines
([`examples/minimal_harness_search.py`](../examples/minimal_harness_search.py)).

An OpenEvolve-style loop plugs in the same way: its `evaluate()` function
POSTs the candidate to `$JUDGE_URL/submit` and returns the judge's score.
Mind the submission budget — evolutionary methods burn evaluations fast,
so give cheap candidates a local pre-filter (your own evaluator, written
from the instruction) and spend submissions on survivors.

## Ready-to-run long-horizon harnesses

[`examples/run_harness.py`](../examples/run_harness.py) supplies concrete,
version-pinned adapters for the three long-horizon patterns above:

```bash
export OPENAI_API_KEY=...
python examples/run_harness.py openevolve --model gpt-5-mini --iterations 100
python examples/run_harness.py codex-goal --model gpt-5.6-terra --token-budget 40000
python examples/run_harness.py coral --model gpt-5.6-terra --agents 2
```

- **OpenEvolve** evolves a task-specific candidate program. Its evaluator
  executes the candidate, POSTs its JSON to Tide, and returns the judge score.
- **Codex Goal mode** uses app-server's `thread/goal/set`, which is the same
  persistent goal state surfaced by `/goal`. The installable
  [`tide-codex-goal-harness`](../examples/harnesses/codex) package keeps the
  JSON-RPC client reusable outside the example runner and lets Codex continue
  until the goal is complete or blocked.
- **CORAL** runs multiple Codex workers over a shared repository. Its packaged
  `TaskGrader` makes `coral eval` spend one Tide submission and returns that
  feedback to the organization.

All three run inside the Harbor task environment and therefore share its time,
submission, and network budgets. Their final reward still comes from Harbor's
verifier. See the [harness README](../examples/harnesses/README.md) for versions,
credentials, and adaptation notes.

## Rules of the game

- **You cannot bring your own judge.** Scores come from the task's judge
  or they don't exist. Different scoring rule = a new task
  ([`tasks/_template`](../tasks/_template)), not a new judge for an
  existing one.
- **Compare methods at the same `budget` tag**, on the same tasks. All
  scores are judge-computed, so the curve comparison is as trustworthy as
  the endpoint comparison. `oracle` and `nop` bracket the plausible range.
- **Sanity-check cheaply**: `--agent oracle` proves the task, `--agent nop`
  proves no leakage, `--fake` exercises your run script with no
  containers — and `--local --command "..."` runs your method against the
  task's real judge with no Docker at all (see the README).
