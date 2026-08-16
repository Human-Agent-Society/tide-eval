# Streams

`tide/stream.py`. A `Stream` runs an ordered list of Harbor tasks under
one agent and carries a state directory between them. Each task runs in a
fresh container with the directory mounted at `$TIDE_STATE_DIR`; whatever
the agent writes there (notes, a skill library, code) is visible in the
next task. tide never reads the contents. Whether carrying that state
helps is what gets measured.

## Use it

```python
from tide import Lab, Stream, metrics

lab = Lab("runs/cl")
stream = Stream(
    "my-stream",
    [
        "tasks/terminal-bench/chess-best-move",
        "tasks/terminal-bench/build-pmars",
        "tasks/terminal-bench/chess-best-move",  # a revisit, for forgetting
    ],
)
rows = await stream.run(
    lab,
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    budget="30m",  # per task; agent/budget/overrides mean what they mean on lab.run
)

df = lab.df("episode")
metrics.learning_curve(df, by=["stream"])
metrics.forgetting(df)
metrics.transfer(df, baseline_df)  # vs the same tasks run isolated
```

The CLI equivalent (also `--fake` / `--local`); a folder target streams
every task inside it in name order:

```bash
tide stream my-stream terminal-bench --agent claude-code --model anthropic/claude-opus-5
```

The supported stream benchmarks are
[terminal-bench 2.0](../../tasks/terminal-bench),
[SWE-bench Verified](../../tasks/swebench-verified), and all six
[CL-Bench](../../tasks/cl-bench) domains. terminal-bench and CL-Bench
tasks are committed to the repo; SWE-bench needs
`tide fetch swebench-verified` first (its upstream has no license, so
those tasks are never committed).

## The stream name

`"my-stream"` is a name you choose; there are no reserved names. It does
three things:

- resume: the name is part of every episode's key, so re-running the
  same name with the same setup picks up where it left off, and a new
  name starts fresh with empty state;
- state: the agent's directory lives under `<lab>/streams/<name>-<variant>/`;
- queries: every row carries the name as a `stream` tag.

The same name under a different agent, tags, or budget is automatically a
different variant with separate state and keys: name your experiment,
not your configuration.

## Ordering

Task order changes continual-learning results, so it is never implicit: a
stream runs exactly the list you give it, and the episode keys pin that
order. The [AgentStream](https://arxiv.org/abs/2608.00155) scenarios map
directly:

- isolated: plain `tide run` over the same tasks (the baseline for
  `metrics.transfer`);
- sequential: list the folders in order;
  `tide stream s1 terminal-bench swebench-verified --agent <a>` runs all
  of one benchmark, then the next;
- interleaved: `--shuffle SEED` shuffles the task list deterministically
  and records the seed as a `shuffle_seed` tag. Each seed is its own
  stream, so the three-seeds-and-average protocol is three runs and one
  groupby:

  ```bash
  for seed in 1 2 3; do
    tide stream mix terminal-bench swebench-verified --shuffle $seed \
      --agent claude-code --model anthropic/claude-opus-5
  done
  ```

In the Python API the order is just the list you build; shuffle it with
`random.Random(seed).shuffle(tasks)` and put the seed in `tags`.

## How state is carried

Harbor mounts the stream's state directory into the agent's container and
sets `$TIDE_STATE_DIR`; `--local` passes the host path itself. Around
each task:

- before it runs, the live directory is reset from the previous task's
  snapshot, so every task starts from a known state, even across crashes;
- after it runs, the ending state is snapshotted, so every task's input
  can be audited later.

On disk, one directory per stream and setup variant:

```
<lab>/streams/<name>-<variant>/
  state/               # the live directory, mounted into the current task
  snapshots/init       # the state before position 0 (seed a memory here)
  snapshots/000, 001…  # each task's ending state
```

`Stream.state_root(lab, agent, ...)` returns that directory for the same
arguments you would pass to `run`.

## Resume

Re-running skips tasks that already have a stored row, like everything
else in tide. A position's key covers the task list up to that position:

- appending tasks extends a finished stream; old positions keep their
  rows, new ones run from the last snapshot;
- editing an earlier position re-runs everything after it. A stream is
  one measurement, and a changed history invalidates what followed.

A stream is sequential by design: each task's starting state is the
previous task's ending state. Distinct streams can run concurrently; the
same stream must not run concurrently with itself.

## Trust

The state directory is agent-written and untrusted. No judge or verifier
ever sees it, so the [trust model](../introduction/design.md) is
unchanged: it can only influence the agent's own future behavior.

## Metrics

All three are ordinary [metrics](metrics.md): pandas functions that
document the columns they expect:

| function | question | expects |
|---|---|---|
| `learning_curve(df)` | does performance rise over the stream? | `position`, `reward` |
| `transfer(stream_df, baseline_df)` | better than the same tasks isolated? | `task`, `reward` in both |
| `forgetting(df)` | did revisited tasks degrade? | `task`, `position`, `reward` |
