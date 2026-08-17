# 🌊 tide

[![CI](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**Autoresearch and continual-learning evaluation on the [Harbor](https://github.com/laude-institute/harbor) task standard.**

More and more of what agents are asked to do requires learning from
inference-time signals: feedback produced during the run itself. tide
evaluates the two forms this takes:
learning from evaluators within one open-ended problem (autoresearch),
and carrying what was learned into the next task (continual learning).

**Autoresearch** is the kind of work DeepMind's
[AlphaEvolve](https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)
and [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) do:
one open-ended optimization problem with a continuous score, hours of
budget, and a judge scoring every submission. There is no "passed",
only *how good, by when*. What improves is **the solution**:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-hero-dark.svg">
  <img src="docs/assets/readme-hero-light.svg" alt="The agent searches however it likes and submits what is worth scoring, within a submission limit. The judge holds all scoring code and data and scores every submission into a log. An optional final judge with hidden tests runs once on the best submission and locks the session. The reward and the submission log land in one table shared by every run, where agents can be compared." width="100%">
</picture>

**Continual learning** puts one agent through a
[stream](docs/api/streams.md) of tasks in order (the
[AgentStream](https://arxiv.org/abs/2608.00155) setting; the supported
benchmarks are [terminal-bench 2.0](tasks/terminal-bench),
[SWE-bench Verified](tasks/swebench-verified), and all six
[CL-Bench](tasks/cl-bench) domains), carrying its memory from task to
task. The signal is what earlier tasks taught: the question is whether
later tasks go better for it. What improves is **the agent**:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-stream-dark.svg">
  <img src="docs/assets/readme-stream-light.svg" alt="One agent works through a stream of tasks in order. Each task runs in its own fresh container and is scored on its own, but the agent's memory directory is carried from task to task, with a snapshot kept at every step. Every task's reward lands in the same table as every other run, so the learning curve over the stream is a single query." width="100%">
</picture>

Tasks are 100% stock Harbor tasks (enforced by test). Agents are anything
that can work inside a container, including your own harness or method.

## Why not plain Harbor?

Harbor solves the hard infrastructure (the task format, running agents
against containers, the ecosystem of agent adapters), and tide uses it as
a library for exactly that. Both modes need five things on top, and they
are the reason tide exists:

| What you want | Plain Harbor | tide |
|---|---|---|
| **The whole score trajectory, not just the endpoint** | One reward number per trial; how the agent got there is lost | The judge records every submission, so the anytime curve, its AUC, and time-to-threshold are one query each, and every point is trusted |
| **Learning across tasks, not only within one** | Every trial starts from zero | A [`Stream`](docs/api/streams.md) carries the agent's memory (a state directory) from task to task, with a snapshot at every step; learning curves, transfer, and forgetting are queries |
| **Compare across budgets** ("what does 8 h buy over 2 h?") | Statistics live inside a single job (pass@k) | Budget is an ordinary tag, so scaling curves are a pivot over any set of runs |
| **Resume from failure on long, multi-day sweeps** | A crash throws the whole job away, and covering a suite × variance × budgets takes days of compute | Re-run the same script and finished episodes are skipped; only the unfinished work re-runs |
| **Compare agents across many runs** | Each run is a throwaway job directory | Every run lands in one table, so comparing agents is a single query that `tide report` reads |

One known limit: resume works at episode granularity. A batch of runs
picks up where it crashed, but a crashed 12-hour episode itself starts
over.

Full design (trust model, task conventions, data model, extensibility):
**[docs/introduction/design.md](docs/introduction/design.md)**.

## Using tide

First run? **[docs/introduction/get-started.md](docs/introduction/get-started.md)** walks from install
to a real agent score, including agent auth and network egress setup.

### Run

```bash
# from source, until the PyPI release lands:
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
pip install -e ".[harbor]"               # container runs; plain -e . covers --local and the API

tide list                                # what's runnable
tide run autoresearch --agent oracle     # oracle = built-in agent that runs each task's reference solution
tide run autoresearch/tsp-tour --agent claude-code --model anthropic/claude-opus-5 --budget 2h     # time (2h / 30m / 90s; bare = hours)
tide run autoresearch/tsp-tour --agent codex --model openai/gpt-5 --max-tokens 500k                # or: tokens / --max-evals / --max-cost
tide stream my-stream terminal-bench --agent claude-code --model anthropic/claude-opus-5               # continual learning: memory carried across tasks
tide report                              # summarize the results store
```

`--budget` is time (`2h` / `30m` / `90s`; a bare number is hours); the other
budget axes are `--max-tokens` (e.g. `500k`), `--max-evals`, and `--max-cost`
(USD). See [budget](docs/api/budget.md).

#### No Docker? Develop locally, verify in containers

`--local` starts the task's **own judge** as a local process and runs
your command against it, with no containers involved:

```bash
tide run autoresearch/circle-packing --local \
  --command "python examples/minimal_harness_search.py" --budget 30s
```

Your command reads `$JUDGE_URL` and `$BUDGET_SEC`, POSTs solutions to
`$JUDGE_URL/submit`, and the judge's verdict is the result, from the same
judge code that runs as a sidecar in containers. Note that local mode has
no isolation: everything, including any hidden tests, is readable on
your own machine. That is acceptable for development, because local
scores are never treated as trusted results; the container run is where
the judge is actually out of reach, and local rows carry a `local://`
uri to mark the difference. Develop locally, report container numbers. (`python examples/quickstart.py`
and `--fake` still work with zero setup, but their scores are simulated.)

When you have Docker, `python examples/run_circle_packing.py` proves the
real pipeline end to end (the oracle must score exactly 0.75), and
`python examples/minimal_harness.py` is the smallest complete container
harness: about twenty-five lines of adapter around the same random-search
loop.

### The Python API

A `Lab` is a directory. Each `run` call is one episode (one Harbor
trial), and `df` returns everything recorded so far as a pandas DataFrame:

```python
# Lab is asyncio-based: run this inside an async function or a notebook.
from tide import Lab, Budget, metrics

lab = Lab("runs/exp1")
row = await lab.run(
    "tasks/autoresearch/circle-packing",  # any task dir or Harbor registry id
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    budget=Budget(time_h=2),  # the budget: time, or tokens / evals / cost
    tags={"suite": "smoke"},  # free-form tags = your schema
)
row.rewards  # the judge's final verdict
row.uri  # the trial directory, for auditing

# Budget is more than a clock; bound whichever resource is scarce:
await lab.run(
    "tasks/autoresearch/circle-packing",
    agent={"name": "codex", "model_name": "openai/gpt-5"},
    budget=Budget(max_tokens=500_000),
)  # or max_evals=50, max_cost_usd=3

curve = metrics.anytime(lab.df("trace"))  # every submission's score, over time
metrics.auc(curve)  # the anytime score
metrics.scaling(
    lab.df("episode"), budget="budget_max_tokens"
)  # what does more budget buy?
metrics.efficiency(
    lab.df("episode"), spend="used_cost_usd"
)  # reward per dollar actually spent
```

Re-running any script resumes it. Reference:
[lab](docs/api/lab.md) · [streams](docs/api/streams.md) ·
[budget](docs/api/budget.md) · [metrics](docs/api/metrics.md) ·
[executors](docs/api/executors.md).

### Continual learning: task streams

A `Stream` runs an ordered task list under one agent. Every task's
container gets the same state directory mounted in (`$TIDE_STATE_DIR`),
so the agent's memory, skill library, or evolved harness is carried from
task to task, and whether that helps is what gets measured:

```python
from tide import Lab, Stream, metrics

lab = Lab("runs/cl")
stream = Stream(
    "my-stream",  # ordered tasks, repeats allowed; the revisit is how forgetting shows
    [
        "tasks/terminal-bench/chess-best-move",
        "tasks/terminal-bench/build-pmars",
        "tasks/terminal-bench/chess-best-move",
    ],
)
rows = await stream.run(
    lab,
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    budget="30m",
)

df = lab.df("episode")
metrics.learning_curve(df, by=["stream"])  # does experience accumulate?
metrics.forgetting(df)  # did the revisited task degrade?
metrics.transfer(df, baseline_df)  # vs the same tasks run isolated (plain lab.run)
```

`"my-stream"` is just a name you choose for the stream: re-running the
same name resumes it, a new name starts fresh with empty memory, and
every row carries the name as a `stream` tag for querying.

Every task in the stream is an ordinary Harbor trial in its own
container. Before each one, the memory is reset to the snapshot from the
previous step; after it, a new snapshot is kept, so a crashed stream
picks up where it left off, and what the agent knew at every step can be
checked later. Adding tasks to the end continues a finished stream;
changing an earlier task re-runs everything after it. Full details:
**[docs/api/streams.md](docs/api/streams.md)**.

### Evaluate your own agent

Every task hands your agent `$JUDGE_URL` and a submission budget;
whichever way you integrate, the task, the judge, and the results store
are identical, so numbers stay comparable across methods:

| You have | Integration |
|---|---|
| a mainstream harness (`claude-code`, `codex`, `aider`, …) | `--agent <name> --model <m>`, zero code |
| your own harness | one `BaseAgent` subclass, referenced via `import_path`; runnable template: [`examples/minimal_harness.py`](examples/minimal_harness.py) |
| OpenEvolve, Codex, or CORAL | version-pinned runnable adapters: [`examples/run_harness.py`](examples/run_harness.py) |
| another method that isn't an "agent" (evolutionary search, a solver) | POST candidates to `$JUDGE_URL/submit`, stop at 429 (about 20 lines) |

The protocol is identical across every task, so one integration covers
the suite. The only thing you cannot bring is your own judge. Full guide
with the `BaseAgent` skeleton and the OpenEvolve pattern:
**[docs/guides/integration.md](docs/guides/integration.md)**.

## Benchmarks

### Autoresearch

| Benchmark | Tasks | Upstream | Run |
|---|---|---|---|
| [first-party](tasks/autoresearch) ↓ | 6 | this repo | `tide run autoresearch --agent <a>` |
| [EdgeBench](tasks/edgebench) | 51 · 2-12 h budgets | [ByteDance-Seed/EdgeBench](https://github.com/ByteDance-Seed/EdgeBench) | `tide run edgebench/<task> --budget <h>` |
| [FrontierCS](tasks/frontier-cs) | 188 algorithmic + 20 research · incl. 4 GPU kernel | [FrontierCS/Frontier-CS](https://github.com/FrontierCS/Frontier-CS) | `tide run frontier-cs/<task> --agent <a>` |

The next converters, vetted for autoresearch fit, are tracked in the
[roadmap](https://github.com/Human-Agent-Society/tide-eval/issues/19).

### Continual learning

Three stream benchmarks. terminal-bench and CL-Bench tasks are committed
to this repo (Apache-2.0) and run out of the box, with a pinned
`fetch.py` to regenerate them; SWE-bench Verified's dataset repo has no
license, so its tasks are fetched onto your machine instead:

| Benchmark | Tasks | Upstream | Run |
|---|---|---|---|
| [terminal-bench](tasks/terminal-bench) | 89 · **v2.0 only** (1.x unsupported) · committed | [terminal-bench-2](https://github.com/laude-institute/terminal-bench-2) (Apache-2.0) | `tide stream my-stream terminal-bench --agent <a>` |
| [SWE-bench Verified](tasks/swebench-verified) | 500 · fetched (upstream has no license) | [harbor-datasets](https://github.com/laude-institute/harbor-datasets) | `tide fetch swebench-verified --limit 50`, then `tide stream my-stream swebench-verified --agent <a>` |
| [CL-Bench](tasks/cl-bench) | 301 · **all 6 domains** · committed | [continual-learning-bench](https://github.com/pgasawa/continual-learning-bench) (Apache-2.0) | `tide stream my-stream tasks/cl-bench/poker-* --agent <a>` |

SWE-bench Verified is there because [AgentStream](https://arxiv.org/abs/2608.00155)
builds its streams from six benchmarks, and it is the hardest of them with
a published Harbor version; the two the paper measures as hardest, HLE
and BrowseComp-Plus, have none yet.
[CL-Bench](tasks/cl-bench) ([paper](https://arxiv.org/pdf/2606.05661)) is
a continual-learning benchmark in the strict sense (sequential instances
of one environment where remembering should help), and its *gain metric*
(stateful minus stateless reward) is `metrics.transfer`. All six
domains are converted, the benchmark's full 301 instances: spectrum
monitoring, sales forecasting, cohort studies, sequential PR bugfixes,
metered database exploration, and heads-up poker against exploitable
opponents. Scoring is the upstream metric in every domain, deterministic
and offline; where a domain has hidden state (the poker deck, the metered
database), it lives in a judge sidecar the agent reaches only over HTTP.
A stream also takes any task list you build yourself, repeats allowed
(that is how forgetting is measured); see
[streams](docs/api/streams.md).

### What each first-party task teaches

Each first-party task teaches one hard part of the autoresearch category
(oracle-verified in real containers, cheat cases re-tested in CI):

| Task | Teaches |
|---|---|
| [`circle-packing`](tasks/autoresearch/circle-packing) | the full protocol; exact-arithmetic grading |
| [`function-minimization`](tasks/autoresearch/function-minimization) | exploration vs local search |
| [`tsp-tour`](tasks/autoresearch/tsp-tour) | combinatorial search, continuous signal |
| [`bin-packing`](tasks/autoresearch/bin-packing) | exact constraint checking |
| [`symbolic-regression`](tasks/autoresearch/symbolic-regression) | the final judge: session on training points, the grade on held-out points |
| [`string-compression`](tasks/autoresearch/string-compression) | safely grading agent-shipped code |

### Define a new task

```bash
cp -r tasks/_template tasks/autoresearch/my-task
pytest tests/test_task_suite.py          # picked up automatically, and already green
```

The template ships as a complete working task, so you start from green
and replace one `TODO(task)` piece at a time: the instruction, one
`score.py` the judge runs on every submission, the submission budget, the
cheat cases, the reference solution, and optionally a `final.py` with
hidden tests, run once on the best submission. GPU tasks add two lines of
config. Guide: **[docs/guides/authoring-tasks.md](docs/guides/authoring-tasks.md)**.

## Contributing

New tasks are the most welcome contribution: copy the template, work the
`TODO(task)` markers, and the suite validates the task for you; see
[define a new task](#define-a-new-task) above and the guide
**[docs/guides/authoring-tasks.md](docs/guides/authoring-tasks.md)**.

For benchmark converters, metrics, and runtime work, use a dev checkout:

```bash
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
uv venv --python 3.12 && uv pip install -e . pytest pytest-asyncio ruff
.venv/bin/python -m pytest tests/ -q     # harbor tests skip if absent
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

PRs are reviewed against the design rules in
[CONTRIBUTING.md](CONTRIBUTING.md).
