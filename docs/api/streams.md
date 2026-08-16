# Streams

`tide/stream.py` — a `Stream` is an ordered list of Harbor tasks run under
one agent, with a **state directory** carried from episode to episode.
Each position is one ordinary episode — one Harbor trial, one container,
one trusted row — and the only thing connecting positions is whatever the
agent wrote into `$TIDE_STATE_DIR`: memory files, a skill library, an
evolved harness. Whether accumulating that state helps is the measurement.

## Use it

```python
# first: tide fetch terminal-bench  (89 pass/fail tasks, pinned to v2.0)
from tide import Lab, Stream, metrics

lab = Lab("runs/cl")
stream = Stream(
    "week1",  # the stream's name — part of every episode's key
    [  # any Harbor tasks, in the order the agent will meet them
        "tasks/terminal-bench/chess-best-move",
        "tasks/terminal-bench/build-pmars",
        "tasks/terminal-bench/chess-best-move",  # a revisit — how forgetting is measured
    ],
)
rows = await stream.run(
    lab,
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    budget="30m",  # per episode; agent/budget/overrides mean what they mean on lab.run
)

df = lab.df("episode")
metrics.learning_curve(df, by=["stream"])  # does experience accumulate?
metrics.forgetting(df)  # did revisited tasks degrade?
metrics.transfer(df, baseline_df)  # vs the same tasks run isolated (plain lab.run)
```

The CLI equivalent (also `--fake` / `--local`) — a folder target streams
every fetched task in name order:

```bash
tide fetch terminal-bench          # or: tide fetch swebench-verified --limit 50
tide stream week1 terminal-bench --agent claude-code --model anthropic/claude-opus-5
```

The supported stream benchmarks are [terminal-bench 2.0](../../tasks/terminal-bench)
(v2.0 only — 1.x predates the Harbor task format),
[SWE-bench Verified](../../tasks/swebench-verified) — the hardest of
[AgentStream](https://arxiv.org/abs/2608.00155)'s six benchmarks with a
published Harbor version — and [CL-bench](../../tasks/cl-bench), whose
sequential per-context turns stream in order under the carried memory
(its rubric judge needs an LLM API key at verify time).

## Ordering: sequential and interleaved streams

Task order changes continual-learning results, so it is never implicit —
a stream runs exactly the list you give it, and the episode keys pin that
order (reordering is a new measurement). The
[AgentStream](https://arxiv.org/abs/2608.00155) scenarios map directly:

- **isolated** — plain `tide run` over the same tasks: the control arm
  `metrics.transfer` compares against;
- **sequential** — benchmark-blocked, like the paper's fixed
  AppWorld → … → Tau2 order: list the folders in order, and
  `tide stream s1 terminal-bench swebench-verified --agent <a>` runs all
  of one benchmark, then the next (within a folder: name order, held
  constant);
- **interleaved** — `--shuffle SEED` deterministically shuffles the union
  and records the seed as a `shuffle_seed` tag. Each seed is its own
  stream — own carried state, own keys, own resume — so the paper's
  three-seeds-and-average protocol is three runs and one groupby:

  ```bash
  for seed in 1 2 3; do
    tide stream mix terminal-bench swebench-verified --shuffle $seed \
      --agent claude-code --model anthropic/claude-opus-5
  done
  ```

  ```python
  metrics.learning_curve(lab.df("episode"), by=["shuffle_seed"])
  ```

In the Python API the order is just the list you build — shuffle it with
`random.Random(seed).shuffle(tasks)` and put the seed in `tags`.

## How state is carried

The executor delivers the stream's state directory into every episode —
Harbor bind-mounts it into the agent's container and points
`$TIDE_STATE_DIR` at it; `--local` hands the host path itself. The agent
reads it at the start of a task and writes whatever it wants its future
self to know. tide never interprets the contents.

Around each position:

- **before** the episode runs, the live state is reset from the previous
  position's snapshot, so every episode's starting state is deterministic
  even across crashes and re-runs;
- **after** it runs, the ending state is snapshotted, so every episode's
  input is auditable and forgetting has evidence.

On disk, under the Lab (one directory per stream × setup variant, so the
same stream name under two agents never shares state):

```
<lab>/streams/<name>-<variant>/
  state/               # the live directory, mounted into the current episode
  snapshots/init       # the state before position 0 (seed a pre-built memory here)
  snapshots/000, 001…  # each position's ending state
```

`Stream.state_root(lab, agent, ...)` returns that directory for the same
arguments you would pass to `run` — write into `<state_root>/state` before
the first run to start the stream from a pre-built memory.

## Resume, and what a position's key covers

Episodes land in the same store, tagged `stream` and `position`, and
re-running skips recorded positions like everything else in tide. The
stream refinement is that a position's key covers the task list *up to
that position*:

- **appending** tasks extends a finished stream — old positions keep their
  rows, new ones run from the last snapshot;
- **editing** an earlier position re-runs everything after it — a stream
  is one measurement, and a changed history invalidates what followed.

A stream is sequential by design: position p+1's starting state is
position p's ending state. Distinct streams (different name, agent, tags,
or budget) run concurrently just fine; never run the *same* stream
variant concurrently with itself.

## Trust

The state directory is agent-authored and untrusted. It is never visible
to any judge or verifier — it can influence only the agent's own future
behavior, so the [trust model](../introduction/design.md) is unchanged:
judge tasks keep their submission logs, pass/fail tasks keep Harbor's
verifier verdict, and a pass is just a 0-or-1 score in the same `reward`
column.

## Metrics

All three are ordinary [metrics](metrics.md) — pure pandas functions
declaring the columns they expect:

| function | question | expects |
|---|---|---|
| `learning_curve(df)` | does performance rise over the stream? | `position`, `reward` |
| `transfer(stream_df, baseline_df)` | better than the same tasks isolated? | `task`, `reward` in both |
| `forgetting(df)` | did revisited tasks degrade? | `task`, `position`, `reward` |

The isolated control arm for `transfer` is a plain `lab.run` sweep over
the same tasks — the same measurement tide always made.
