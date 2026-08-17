# Get started

Install to a real score, in both modes. For the ideas behind the
pipeline see [design](design.md); for evaluating your own agent see
[running agents](running-agents.md).

## Install

```bash
pip install "tide-eval[harbor]"    # benchmark tasks download on first use
# or from source, with every task already in tasks/:
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
pip install -e ".[harbor]"
```

Docker runs the tasks. One caveat: many tasks use an `allowlist` network
policy, enforced with an nftables egress sidecar; Docker Desktop older
than ~4.30 lacks the kernel support and Harbor will refuse the run (see
[troubleshooting](#troubleshooting)).

## Run a task

The `oracle` agent runs a task's reference solution in-container, with
no keys and no network, so it isolates the plumbing. Start there:

```bash
tide list                                 # what's runnable
tide run cl-bench/bsm-s01 --agent oracle  # must score exactly 1.0
```

Then a real agent (its CLI runs inside the container and needs
credentials and network egress; see
[running agents](running-agents.md)):

```bash
tide run frontier-cs/frontier-cs-algorithm-1 --agent claude-code --model anthropic/claude-opus-5 --budget 2h
```

## Budgets

A run is bounded by whichever resource is scarce; set that one and leave
the rest unset:

| Axis | CLI flag | `Budget` field | Enforcement |
|---|---|---|---|
| time | `--budget` (`2h`, `30m`, `90s`; bare = hours) | `time_h` | hard: the container timeout; the deadline is a normal ending, the verifier still grades what exists |
| evals | `--max-evals` | `max_submissions` | hard at the task's own ceiling (the judge returns 429 past it); a lower per-run cap is signalled |
| tokens | `--max-tokens` (`500k`, `2m`) | `max_tokens` | soft: signalled, actual spend recorded |
| cost (USD) | `--max-cost` | `max_cost_usd` | soft: signalled, actual spend recorded |

Each axis reaches the agent's container as a `TIDE_*` environment
variable, is tagged on the episode (`budget`, `budget_max_tokens`, ...)
so runs group by it, and the actual spend comes back as `used_*`
columns: submission counts from the judge's log, token and cost totals
from the harness's own usage report, the numbers the provider billed.
The rule is to trust the measurement, not the promise.

## Streams

A stream is continual learning: an ordered task list under one agent,
with a state directory carried from task to task and mounted into every
container as `$TIDE_STATE_DIR`. tide never reads it; whether carrying it
helps is what gets measured.

```bash
tide stream demo cl-bench --agent claude-code --model anthropic/claude-opus-5
tide stream mix terminal-bench cl-bench --shuffle 1 --agent claude-code --model anthropic/claude-opus-5
```

The stream name is yours to choose. Re-running the same name resumes it;
a new name starts fresh; the same name under a different agent, tags, or
budget is automatically a separate variant with its own state. Order is
never implicit: a stream runs exactly the list you give it, and
`--shuffle SEED` shuffles it deterministically, recording the seed as a
tag (each seed is its own stream).

Around each task, the live state directory is reset from the previous
snapshot before the run and snapshotted after, so a crashed stream picks
up where it left off and every step's memory can be audited later:

```
<lab>/streams/<name>-<variant>/
  state/               # mounted into the current task
  snapshots/init       # the state before position 0 (seed a memory here)
  snapshots/000, 001…  # each task's ending state
```

Appending tasks extends a finished stream; editing an earlier position
re-runs everything after it.

## The Python API

A `Lab` is a directory holding one results table. Each `run` is one
episode (one Harbor trial); `df` returns everything recorded so far as a
pandas DataFrame:

```python
from tide import Budget, Lab, Stream, metrics

lab = Lab("runs/exp1")
row = await lab.run(  # asyncio: inside an async function or a notebook
    "tasks/autoresearch/frontier-cs/frontier-cs-algorithm-1",
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    budget=Budget(time_h=2),  # or max_tokens=..., max_evals=..., max_cost_usd=...
    tags={"suite": "smoke"},  # free-form tags = your result schema
)
row.rewards  # the trusted verdict
row.uri  # the trial directory, for auditing

stream = Stream("demo", ["tasks/continual-learning/cl-bench/bsm-s01", "..."])
await stream.run(lab, agent={"name": "claude-code"}, budget="30m")

df = lab.df("episode")
df.groupby(["model", "task"])["reward"].mean()
```

Every run, from any script and any day, appends to the same table, so
comparing agents is a query and [metrics](metrics.md) are functions over
it. `lab.run_many([...])` runs a batch with bounded concurrency;
`lab.df("trace")` returns the judge's per-submission log.

## Resume

Every episode gets a stable key derived from (task, agent, tags, budget,
overrides). A key that already has a row is skipped and the stored row
returned, so re-running any crashed script or stream picks up where it
left off. Vary a tag (`--tag attempt=2`) to add attempts instead. The
store is append-only, and resume is episode-granular: a half-finished
episode starts over, because a run stitched from checkpoints would not
be comparable to a clean budget.

## No Docker? Local and fake runs

`--local` starts the task's own judge as a local process and runs your
command against it:

```bash
tide run autoresearch/first-party/circle-packing --local \
  --command "python examples/minimal_harness_search.py" --budget 30s
```

Same judge code as the container sidecar, but no isolation (even hidden
tests are readable on your machine), so local rows carry a `local://`
uri and are never trusted results. Develop locally, report container
numbers. `--fake` and `python examples/quickstart.py` need no setup at
all; their scores are simulated.

## Where the data lands

A `Lab` is a directory (`--lab`, default `runs/cli`):

```
runs/cli/
├── results.sqlite                  # one table: episode rows + trace rows
└── trials/<task>__<id>/
    ├── agent/trajectory.json       # every step + tokens, cost, duration
    ├── verifier/reward.json        # the final verdict
    ├── verifier/submissions.jsonl  # every judge-scored submission, with t
    └── result.json, config.json, trial.log
```

`tide report` summarizes the store; every row's `uri` points back at its
trial directory, so any number can be audited to its evidence.

## Troubleshooting

- **`Cannot connect to the Docker daemon`**: start Docker first.
- **`network_mode='allowlist' is not supported by EnvironmentType.DOCKER`**:
  your Docker VM kernel lacks nftables FIB rules (Docker Desktop <= ~4.30).
  Upgrade Docker; until then `--local` develops against the real judge.
- **An agent CLI fails during setup with npm/apt errors**: its install
  hosts are missing from the allowlist, or the setup timeout is too
  small; see [running agents](running-agents.md#network-egress).
- **An agent CLI fails immediately with 401**: no credentials; see
  [running agents](running-agents.md#credentials).
