# 🌊 tide

[![CI](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**Autoresearch evaluation on the [Harbor](https://github.com/laude-institute/harbor) task standard.**

**English** | [中文](README_CN.md)

Autoresearch tasks — the kind of work DeepMind's
[AlphaEvolve](https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)
and [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) do — are open-ended optimization
problems: hours of budget, a continuous score, and an agent iterating
toward a better solution the whole way. There is no "passed" — only *how
good, by when*. tide evaluates that regime honestly:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-hero-dark.svg">
  <img src="docs/assets/readme-hero-light.svg" alt="The agent searches however it likes and submits what is worth scoring, within a submission limit. The judge holds all scoring code and data and scores every submission into a log. An optional final judge with hidden tests runs once on the best submission and locks the session. The reward and the submission log land in one table shared by every run, where agents can be compared." width="100%">
</picture>

Tasks are 100% stock Harbor tasks (enforced by test). Agents are anything
that can work inside a container — including your own harness or method.

## Why not plain Harbor?

Harbor solves the hard infrastructure — the task format, running agents
against containers, the ecosystem of agent adapters — and tide uses it as
a library for exactly that. Autoresearch needs four things on top, and
they are the reason tide exists:

| Plain Harbor | tide |
|---|---|
| One reward number per trial; how the agent got there is lost | The judge scores and records every submission, so the anytime curve, its AUC, and time-to-threshold are one query each — and every point on them is trusted |
| Statistics live inside a single job (pass@k) | Budget is an ordinary tag, so "what does 8 h buy over 2 h?" is a query across any set of runs |
| One task, one run — and covering the suite, repeating for variance, or scanning budgets multiplies that into days of compute, which a crash throws away | Run the same script again and finished episodes are skipped automatically, so only the unfinished work re-runs |
| Each run is a throwaway job directory | Every run lands in the same table, so comparing agents across runs is a single query — `tide report` reads it |

One honest limit: resume works at episode granularity. A batch of runs
picks up where it crashed, but a crashed 12-hour episode itself starts
over.

Full design — trust model, task conventions, data model, extensibility:
**[docs/design.md](docs/design.md)**.

## Using tide

### Run

```bash
# from source, until the PyPI release lands (see Roadmap):
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
pip install -e ".[harbor]"               # container runs; plain -e . covers --local and the API

tide list                                # what's runnable
tide run autoresearch --agent oracle     # oracle = built-in agent that runs each task's reference solution
tide run edgebench/ann_vector_search_qps --agent codex --budget 2   # hours
tide report                              # summarize the results store
```

#### No Docker? Develop locally, verify in containers

`--local` starts the task's **own judge** as a local process and runs
your command against it, with no containers involved:

```bash
tide run autoresearch/circle-packing --local \
  --command "python examples/minimal_harness_search.py" --budget 0.01
```

Your command reads `$JUDGE_URL` and `$BUDGET_SEC`, POSTs solutions to
`$JUDGE_URL/submit`, and the judge's verdict is the result — the same
judge code that runs as a sidecar in containers. Local rows carry a
`local://` uri because the judge ran on a machine the agent also controls:
develop locally, report container numbers. (`python examples/quickstart.py`
and `--fake` still work with zero setup, but their scores are simulated.)

When you have Docker, `python examples/run_circle_packing.py` proves the
real pipeline end to end — the oracle must score exactly 0.75 — and
`python examples/minimal_harness.py` is the smallest complete container
harness: about twenty-five lines of adapter around the same random-search
loop.

### The Python API

A `Lab` is a directory. Each `run` call is one episode (one Harbor
trial), and `df` returns everything recorded so far as a pandas DataFrame:

```python
# Lab is asyncio-based: run this inside an async function or a notebook.
from tide import Lab, metrics

lab = Lab("runs/exp1")
row = await lab.run(
    "tasks/autoresearch/circle-packing",  # any task dir or Harbor registry id
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    tags={"budget": 2},  # free-form tags = your schema
)
row.rewards  # trusted score          row.uri → the auditable trial dir

curve = metrics.anytime(lab.df("trace"))  # every submission's score, over time
metrics.auc(curve)  # the anytime score
metrics.scaling(lab.df("episode"))  # what does more budget buy?
```

Re-running any script resumes it. Reference:
[lab](docs/components/lab.md) · [metrics](docs/components/metrics.md) ·
[executors](docs/components/executors.md).

### Evaluate your own agent

Every task hands your agent `$JUDGE_URL` and a submission budget;
whichever way you integrate, the task, the judge, and the results store
are identical — so numbers stay comparable across methods:

| You have | Integration |
|---|---|
| a mainstream harness (`claude-code`, `codex`, `aider`, …) | `--agent <name> --model <m>` — zero code |
| your own harness | one `BaseAgent` subclass, referenced via `import_path` — runnable template: [`examples/minimal_harness.py`](examples/minimal_harness.py) |
| a method that isn't an "agent" (OpenEvolve-style search, a solver) | POST candidates to `$JUDGE_URL/submit`, stop at 429 — ~20 lines |

The protocol is identical across every task, so one integration covers
the suite. The only thing you cannot bring is your own judge. Full guide
with the `BaseAgent` skeleton and the OpenEvolve pattern:
**[docs/integration.md](docs/integration.md)**.

## Tasks

| Benchmark | Tasks | Run |
|---|---|---|
| [first-party](tasks/autoresearch) ↓ | 6 | `tide run autoresearch --agent <a>` |
| [EdgeBench](tasks/edgebench) | 51 · 2–12 h budgets | `tide run edgebench/<task> --budget <h>` |
| [FrontierCS 2.0](tasks/frontier-cs) | 20 · incl. 4 GPU kernel | `python examples/run_frontiercs.py` |
| [AlgoTune](https://github.com/oripress/AlgoTune) | 154 · via Harbor registry | `tide run algotune/<task> --agent <a>` |

Each first-party task teaches one hard part of the category
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
pytest tests/test_task_suite.py          # picked up automatically — and already green
```

The template ships as a complete working task, so you start from green
and replace one `TODO(task)` piece at a time: the instruction, one
`score.py` the judge runs on every submission, the submission budget, the
cheat cases, the reference solution — and optionally a `final.py` with
hidden tests, run once on the best submission. GPU tasks add two lines of
config. Guide: **[docs/components/tasks.md](docs/components/tasks.md)**.

## Roadmap

- [ ] PyPI release (`tide-eval` — name reserved, not yet published)
- [ ] GPU exemplar task, oracle-gated in CI
- [ ] Harbor pin-upgrade workflow
- [ ] More autoresearch converters
- [ ] Hosted results viewer
- [ ] Beyond autoresearch: continual-learning streams and live tasks — as
  [extensions](docs/design.md#extensibility), not rewrites

## Development & contributing

```bash
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
uv venv --python 3.12 && uv pip install -e . pytest pytest-asyncio ruff
.venv/bin/python -m pytest tests/ -q     # harbor tests skip if absent
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Contributions are welcome — new tasks especially. The design rules PRs
are reviewed against are in [CONTRIBUTING.md](CONTRIBUTING.md).
License: [Apache-2.0](LICENSE)
