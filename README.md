# 🌊 tide

[![CI](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**Evaluation infrastructure for self-evolving agents, on the [Harbor](https://github.com/laude-institute/harbor) task standard.**

An agent self-evolves when something it learned during a run persists
past it: memory, a skill library, an evolved harness, updated weights.
tide measures whether anything actually persisted, in the two task
regimes where that shows up. The method does the learning; tide does the
measurement ([why, in detail](docs/design.md)).

**Autoresearch** is the kind of work DeepMind's
[AlphaEvolve](https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)
and [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) do:
one open-ended optimization problem with a continuous score, hours of
budget, and a judge scoring every submission. There is no "passed",
only *how good, by when*. The question is what the agent accumulates
before the budget ends:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-hero-dark.svg">
  <img src="docs/assets/readme-hero-light.svg" alt="The agent searches however it likes and submits what is worth scoring, within a submission limit. The judge holds all scoring code and data and scores every submission into a log. An optional final judge with hidden tests runs once on the best submission and locks the session. The reward and the submission log land in one table shared by every run, where agents can be compared." width="100%">
</picture>

**A stream of tasks** puts one agent through a
[stream](docs/get-started.md#streams) of tasks in order (the
[AgentStream](https://arxiv.org/abs/2608.00155) setting), carrying its
memory from task to task. The question is what carries into the next task:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-stream-dark.svg">
  <img src="docs/assets/readme-stream-light.svg" alt="One agent works through a stream of tasks in order. Each task runs in its own fresh container and is scored on its own, but the agent's memory directory is carried from task to task, with a snapshot kept at every step. Every task's reward lands in the same table as every other run, so the learning curve over the stream is a single query." width="100%">
</picture>

Tasks are 100% stock Harbor tasks (enforced by test). Agents are anything
that can work inside a container, including your own harness or method.

## Why not plain Harbor?

Harbor runs the trial, and tide imports it for that: task format,
containers, agent adapters, the verifier, trajectories, `harbor job
resume`, `harbor view`. Four things sit on top.

| What tide adds | Why | Where |
|---|---|---|
| A judge the agent can submit to whenever it likes, which scores and timestamps every submission | Harbor scores a trial where the task says to, and the reward has no time attached to it. The judge's log is the anytime curve, and the judge is what computed it | [`judge_server.py`](tasks/_template/environment/judge_server.py) |
| Streams, which run an ordered task list and snapshot the carried state after each position | Every task therefore starts from a state you can point at, a stream that crashes resumes from its last snapshot, and adding a task to a finished stream only runs the new one | [`stream.py`](tide/stream.py), [streams](docs/get-started.md#streams) |
| One append-only table holding every run, keyed by (task, agent, tags) | Comparing scores against budget, one benchmark against another, or a stream against its stateless baseline is a query over the same rows, and re-running a script skips whatever already finished | [`store.py`](tide/store.py), [`lab.py`](tide/lab.py) |
| Budgets on four axes, and metrics that are ordinary functions over the table | Bound a run by time, evals, tokens or cost, then ask it for an AUC, a time-to-threshold, transfer or forgetting | [`budget.py`](tide/budget.py), [metrics](docs/metrics.md) |

Resume is episode-granular: a crashed 12-hour episode starts over.

Full design (trust model, task conventions, data model, extensibility):
**[docs/design.md](docs/design.md)**.

## Using tide

First run? **[docs/get-started.md](docs/get-started.md)** walks from install
to a scored task. Pointing a real agent at one needs two things, both in
**[docs/running-agents.md](docs/running-agents.md)**: API credentials inside
the container, and the hosts its network policy must allow. The full docs
read in order from **[docs/](docs/README.md)**.

### Run

```bash
pip install "tide-eval[harbor]"    # or from a source checkout: pip install -e ".[harbor]"

tide list                          # what's runnable
tide fetch cl-bench                # download a benchmark's tasks (a source checkout has them all already)
tide run frontier-cs/frontier-cs-2-0-vllm-llm-serving-optimization --agent claude-code --model anthropic/claude-opus-5 --budget 2h
tide stream cl-bench --agent claude-code --model anthropic/claude-opus-5
```

`--budget` is time (`2h` / `30m` / `90s`; a bare number is hours); the other
budget axes are `--max-tokens` (e.g. `500k`), `--max-evals`, and `--max-cost`
(USD). See [budgets](docs/get-started.md#budgets).

#### No Docker? Develop locally, verify in containers

`--local` starts the task's **own judge** as a local process and runs
your command against it, with no containers involved:

```bash
tide run autoresearch/first-party/circle-packing --local \
  --command "python examples/minimal_harness_search.py" --budget 30s
```

Your command reads `$JUDGE_URL` and `$BUDGET_SEC` and POSTs solutions to
`$JUDGE_URL/submit`; the same judge code that runs as a container sidecar
scores them. Local mode has no isolation (even hidden tests are readable
on your machine), so local rows carry a `local://` uri and are never
trusted results. Develop locally, report container numbers.

With Docker, `tide run cl-bench/bsm-s01 --agent oracle` proves the real
pipeline end to end (the oracle runs the task's reference solution and
must score exactly 1.0), and
[`examples/minimal_harness.py`](examples/minimal_harness.py) is the
smallest complete container harness.

### The Python API

A `Lab` is a directory. Each `run` call is one episode (one Harbor
trial), and `df` returns everything recorded so far as a pandas DataFrame:

```python
# Lab is asyncio-based: run this inside an async function or a notebook.
from tide import Lab, Budget, metrics

lab = Lab("runs/exp1")
row = await lab.run(
    "tasks/autoresearch/frontier-cs/frontier-cs-2-0-vllm-llm-serving-optimization",  # any task dir or Harbor registry id
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    budget=Budget(
        time_h=2
    ),  # or max_tokens=500_000, max_submissions=50, max_cost_usd=3
    tags={"suite": "smoke"},  # free-form tags = your schema
)
row.rewards  # the judge's final verdict
row.uri  # the trial directory, for auditing

curve = metrics.anytime(lab.df("trace"))  # every submission's score, over time
metrics.auc(curve)  # the anytime score
```

Re-running any script resumes it. Reference:
[get started](docs/get-started.md) · [metrics](docs/metrics.md).

### Task streams

A `Stream` runs an ordered task list under one agent. Every task's
container mounts the same state directory (`$TIDE_STATE_DIR`), carrying
the agent's memory, skill library, or evolved harness from task to task:

```python
from tide import Lab, Stream, metrics

lab = Lab("runs/cl")
stream = Stream(
    "my-stream",  # the name; a new one reruns the same tasks from empty memory
    [  # ordered tasks, repeats allowed; the revisit is how forgetting shows
        "tasks/continual-learning/terminal-bench/chess-best-move",
        "tasks/continual-learning/terminal-bench/build-pmars",
        "tasks/continual-learning/terminal-bench/chess-best-move",
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

Re-running the same stream resumes it. A stream's identity is its name plus
its agent, tags, budget, and task list; changing any of those makes a
separate stream with its own memory, and a new name reruns the same tasks
from empty memory. On the CLI that name is `--name`, defaulting to one
derived from the targets. Each task is an ordinary Harbor trial in its own
container, with memory snapshotted at every step, so a crashed stream
resumes where it left off. Full details:
**[docs/get-started.md](docs/get-started.md#streams)**.

### Evaluate your own agent

Every task hands your agent `$JUDGE_URL` and a submission budget. Whichever
way you integrate, the task, judge, and results store are identical, so
numbers stay comparable across methods:

| You have | Integration |
|---|---|
| a mainstream harness (`claude-code`, `codex`, `aider`, …) | `--agent <name> --model <m>`, zero code |
| your own harness | one `BaseAgent` subclass, referenced via `import_path`; runnable template: [`examples/minimal_harness.py`](examples/minimal_harness.py) |
| OpenEvolve, Codex, or CORAL | version-pinned runnable adapters: [`examples/run_harness.py`](examples/run_harness.py) |
| another method that isn't an "agent" (evolutionary search, a solver) | POST candidates to `$JUDGE_URL/submit`, stop at 429 (about 20 lines) |

The only thing you cannot bring is your own judge. Full guide:
**[docs/running-agents.md](docs/running-agents.md)**.

### Examples

[`quickstart.py`](examples/quickstart.py) and
[`stream_quickstart.py`](examples/stream_quickstart.py) run with zero setup;
[`minimal_harness.py`](examples/minimal_harness.py) is the smallest real
harness and needs Docker and `[harbor]`;
[`examples/harnesses`](examples/harnesses) adds OpenEvolve, Codex, and CORAL
as baselines. What each shows: [`examples/`](examples/README.md).

## Benchmarks

### Autoresearch

| Benchmark | Tasks | Upstream | Run |
|---|---|---|---|
| [first-party](tasks/autoresearch/first-party) | 6 | this repo | `tide run autoresearch/first-party --agent <a>` |
| [EdgeBench](tasks/autoresearch/edgebench) | 51 · 2-12 h budgets | [ByteDance-Seed/EdgeBench](https://github.com/ByteDance-Seed/EdgeBench) | `tide run edgebench/<task> --budget <h>` |
| [FrontierCS](tasks/autoresearch/frontier-cs) | 188 algorithmic + 20 research · incl. 4 GPU kernel | [FrontierCS/Frontier-CS](https://github.com/FrontierCS/Frontier-CS) | `tide run frontier-cs/<task> --agent <a>` |

Each first-party task teaches one hard part of the category (held-out
grading, safely grading agent-shipped code, ...); [docs/tasks.md](docs/tasks.md)
has the full catalog with oracle scores. The
[roadmap](https://github.com/Human-Agent-Society/tide-eval/issues/19) tracks
the next converters.

### Task streams

Three stream benchmarks. terminal-bench and CL-Bench tasks are committed
to this repo (Apache-2.0) and run out of the box, with a pinned
`fetch.py` to regenerate them; SWE-bench Verified's dataset repo has no
license, so its tasks are fetched onto your machine instead:

| Benchmark | Tasks | Upstream | Run |
|---|---|---|---|
| [terminal-bench](tasks/continual-learning/terminal-bench) | 89 · **v2.0 only** (1.x unsupported) · committed | [terminal-bench-2](https://github.com/laude-institute/terminal-bench-2) (Apache-2.0) | `tide stream terminal-bench --agent <a>` |
| [SWE-bench Verified](tasks/continual-learning/swebench-verified) | 500 · fetched (upstream has no license) | [harbor-datasets](https://github.com/laude-institute/harbor-datasets) | `tide fetch swebench-verified --limit 50`, then `tide stream swebench-verified --agent <a>` |
| [CL-Bench](tasks/continual-learning/cl-bench) | 301 · **all 6 domains** · committed | [continual-learning-bench](https://github.com/pgasawa/continual-learning-bench) (Apache-2.0) | `tide stream cl-bench --agent <a>` |

SWE-bench Verified is the hardest of the benchmarks
[AgentStream](https://arxiv.org/abs/2608.00155) builds its streams from
that has a published Harbor version.
[CL-Bench](tasks/continual-learning/cl-bench) ([paper](https://arxiv.org/pdf/2606.05661)) is
a continual-learning benchmark in the strict sense: sequential instances
of one environment where remembering should help, scored by the upstream
metric in every domain (its *gain metric* is `metrics.transfer`). Where a
domain has hidden state (the poker deck, the metered database), it lives
in a judge sidecar the agent reaches only over HTTP. A stream also takes
any task list you build yourself, repeats allowed; see
[streams](docs/get-started.md#streams).

### Define a new task

```bash
mkdir -p tasks/autoresearch/my-suite     # a new benchmark is just a folder
cp -r tasks/_template tasks/autoresearch/my-suite/my-task
pytest tests/test_task_suite.py          # picked up automatically, and already green
```

The template ships as a complete working task: replace one `TODO(task)`
piece at a time and the suite keeps validating it. A benchmark is just a
directory of such tasks; `fetch.register(name, repo, ref)` makes a
git-hosted one downloadable by name, the way gym environments register.
Guide: **[docs/authoring-tasks.md](docs/authoring-tasks.md)**.

## Contributing

New tasks are the most welcome contribution; see
[define a new task](#define-a-new-task) above.

For benchmark converters, metrics, and runtime work,
[CONTRIBUTING.md](CONTRIBUTING.md) has the dev setup and the design rules
PRs are reviewed against.
