# 🌊 tide

[![CI](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**Autoresearch evaluation on the [Harbor](https://github.com/laude-institute/harbor) task standard.**

**English** | [中文](README_CN.md)

Autoresearch tasks — the AlphaEvolve / OpenEvolve style of workload — are
open-ended optimization problems: hours of budget, a continuous score, and
an agent that evaluates itself hundreds of times along the way. There is no "passed" — only *how good, by when*. tide
evaluates that regime honestly:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-hero-dark.svg">
  <img src="docs/assets/readme-hero-light.svg" alt="The agent scores itself freely and its score log climbs. At the isolation line, the solution crosses but the claimed score is stopped with an X. The verifier re-scores the solution from scratch, and the trusted score lands in one accumulating table where curves are queries." width="100%">
</picture>

Tasks are 100% stock Harbor tasks (enforced by test). Agents are anything
that can work inside a container — including your own harness or method.

## Why not plain Harbor?

Harbor is very good at one thing — scoring an agent on one task, once, in
a way you can trust — and tide uses it as a library for exactly that.
Autoresearch needs four things on top, and they are the reason tide exists:

| Plain Harbor | tide |
|---|---|
| One reward number per trial; the agent's self-eval curve is lost | The score log becomes `trace` rows, so the anytime curve, its AUC, and time-to-threshold are one query each |
| Statistics live inside a single job (pass@k) | Budget is an ordinary tag, so "what does 8 h buy over 2 h?" is a query across any set of runs |
| A crashed sweep restarts from zero | Idempotency keys skip finished episodes on re-run — which matters when one episode costs hours |
| Each run is a throwaway job directory | One append-only store accretes for weeks, and `tide report` reads it |

One honest limit: resume works at episode granularity. A sweep picks up
where it crashed, but a crashed 12-hour episode itself starts over.

Full design — trust model, task conventions, data model, extensibility:
**[docs/design.md](docs/design.md)**.

## Run

```bash
# from source, until the PyPI release lands (see Roadmap):
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
pip install -e ".[harbor]"               # container runs; plain -e . covers --local and the API

tide list                                # what's runnable
tide run autoresearch --agent oracle     # oracle = built-in agent that runs each task's reference solution
tide run edgebench/ann_vector_search_qps --agent codex --budget 2   # hours
tide report                              # summarize the results store
```

### No Docker? Develop locally, verify in containers

`--local` runs your own method against the task's **real scorer and real
grader** on your machine, with no containers involved:

```bash
tide run autoresearch/circle-packing --local \
  --command "python examples/minimal_harness_search.py" --budget 0.01
```

Your command reads two environment variables — `$APP`, the working
directory where `scorer.py` and `best/` live, and `$BUDGET_SEC` — and when
it finishes (or the budget kills it), the task's real `grade.py` scores
whatever it left behind. Local rows carry a `local://` uri because nothing
is isolated: they are for developing your method, and the number you
report should come from a container run. (`python examples/quickstart.py`
and `--fake` still work with zero setup, but their scores are simulated.)

When you have Docker, `python examples/run_circle_packing.py` proves the
real pipeline end to end — the oracle must score exactly 0.75 — and
`python examples/minimal_harness.py` is the smallest complete container
harness: about thirty lines of adapter around the same random-search loop.

## Use the API

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

curve = metrics.anytime(lab.df("trace"))  # the agent's own scores over time
metrics.auc(curve)  # the anytime score
metrics.scaling(lab.df("episode"), by=["model"])  # what does more budget buy?
```

Re-running any script resumes it. Reference:
[lab](docs/components/lab.md) · [metrics](docs/components/metrics.md) ·
[executors](docs/components/executors.md).

## Evaluate *your* agent

Whichever way you integrate, the task, the isolated verifier, and the
results store are identical — so numbers stay comparable across methods:

| You have | Integration |
|---|---|
| a mainstream harness (`claude-code`, `codex`, `aider`, …) | `--agent <name> --model <m>` — zero code |
| your own harness | one `BaseAgent` subclass, referenced via `import_path` — runnable template: [`examples/minimal_harness.py`](examples/minimal_harness.py) |
| a method that isn't an "agent" (OpenEvolve-style search, a solver) | keep your best solution at the artifact path; optionally log self-scores |

The container contract is identical across all six first-party tasks, so
one integration covers the suite. The only thing you cannot bring is your
own grader. Full guide with the `BaseAgent` skeleton and a worked
OpenEvolve example: **[docs/integration.md](docs/integration.md)**.

## Define a new task

```bash
cp -r tasks/_template tasks/autoresearch/my-task
pytest tests/test_task_suite.py          # picked up automatically — and already green
```

The template ships as a complete working task, so you start from green and
replace one `TODO(task)` piece at a time (config, instruction, public
scorer, private grader, cheat cases, oracle solution). GPU tasks add two
lines of config. Guide: **[docs/components/tasks.md](docs/components/tasks.md)**.

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
| [`symbolic-regression`](tasks/autoresearch/symbolic-regression) | anti-overfitting: graded on held-out points |
| [`string-compression`](tasks/autoresearch/string-compression) | safely grading agent-shipped code |

## Roadmap

- [ ] PyPI release (`tide-eval` — name reserved, not yet published)
- [ ] GPU exemplar task, oracle-gated in CI
- [ ] Harbor pin-upgrade workflow
- [ ] More autoresearch converters
- [ ] Hosted results viewer
- [ ] Beyond autoresearch: continual-learning streams and live tasks — as
  [extensions](docs/design.md#extensibility), not rewrites

## Development

```bash
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
uv venv --python 3.12 && uv pip install -e . pytest pytest-asyncio ruff
.venv/bin/python -m pytest tests/ -q     # harbor tests skip if absent
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Design rules for PRs: [CONTRIBUTING.md](CONTRIBUTING.md) ·
License: [Apache-2.0](LICENSE)
