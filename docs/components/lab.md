# Lab & store

`tide/lab.py` · `tide/store.py` — **the frozen interface**: everything else
in tide, and everything users build, depends on exactly two things — the
signature of `Lab.run`, and the results table. Change anything here as an
addition, never a mutation.

## Use it

```python
from tide import Lab

lab = Lab("runs/exp1")  # a Lab IS a directory: results.sqlite + trials/

row = await lab.run(  # one episode = one trusted score
    "tasks/autoresearch/tsp-tour",
    agent={"name": "oracle"},
    tags={"budget": 1},  # free-form tags = your result schema
)
rows = await lab.run_many([...])  # many episodes, concurrency-bounded
df = lab.df("episode")  # the store as pandas
```

Three things to know about `run`:

- **Re-running = resuming.** Every episode gets a stable ID, auto-derived
  from (task, agent, tags, overrides) or passed as `key=`. If that ID is
  already in the table, nothing executes and the stored row is returned —
  so running the same script again picks up where it crashed. (Engineers
  know this pattern as an idempotency key.)
- **Trace comes for free.** The judge's submission log is stored as
  `<key>#t<i>` rows of kind `trace`, next to the `episode` row — every
  point judge-scored, so the curve is trusted.
- **`**overrides` reach the executor** — for Harbor, these are
  `TrialConfig` fields (e.g. `verifier={...}`).

## Results accumulate

Every `run` — from any script, any day, the CLI or the API — appends a row
to the same `results.sqlite`, tagged with whatever dimensions you chose.
Monday's claude-code sweep, Thursday's prompt tweak, and next week's codex
run are not three job directories; they are rows in one table that differ
only in their tags. Comparing them is a query, not archaeology:

```python
lab.df("episode").groupby(["model", "task"])["reward"].mean()
```

Accumulation and resume are the same mechanism: a re-run of Thursday's
crashed sweep finds most of its keys already in the table and only runs
what's missing. And nothing about where a number came from is lost —
every row's `uri` still points at the full Harbor trial directory. Harbor
treats each run as a printed report; a Lab is the notebook they are all
recorded in.

## The row model

| kind | one row per | key shape | source |
|---|---|---|---|
| `episode` | one task run (= one Harbor trial) | `<key>` | the judge's final verdict |
| `trace` | one submission | `<key>#t<i>` | the judge's submission log |

`kind` is an open string: a future evaluation regime adds new kinds (with
their own key shapes) without any schema change.

`df()` expands tags and rewards into columns. On name collisions, base
columns win over tags, tags over rewards; the losers get a `tag_` /
`reward_` prefix, so every column stays 1-dimensional.

## Invariants (do not break)

1. **Append-only.** The one sanctioned delete is `delete_prefix("<key>#")` —
   clearing a retried episode's partial trace before re-running.
2. **The run ID is exact.** Changing what "the same episode" means breaks
   every user's resume behavior.
3. **Raw scores only.** Normalization lives in `tide/metrics.py`, at query
   time.
4. **Duplicate keys raise.** A silent overwrite would corrupt resumes.

## Extend it

- **New row kind**: pick a kind string and a distinct key shape, write rows,
  filter with `df(kind=…)`. No schema change.
- **New key policy**: pass `key=` from your script — don't change
  `_default_key`.
- **New backend**: that's an [executor](executors.md), not a Lab change.
- **New columns**: fine (old rows read as NULL). Renames/retypes: never.
