# Metrics

`tide/metrics.py` — pure functions, `DataFrame in → DataFrame/Series out`.
They import pandas and **nothing from tide**, so they work on any exported
results table, including one you didn't produce.

## Use them

```python
from tide import Lab, metrics

lab = Lab("runs/exp1")
ep, trace = lab.df("episode"), lab.df("trace")

curve = metrics.anytime(trace, by=["task"])  # best-so-far over time
metrics.auc(curve[curve.task == "tsp-tour"])  # the anytime score
metrics.scaling(ep, by=["model"])  # score vs budget
metrics.improvements(trace, by=["task"])  # how often self-eval improved
```

| Function | Expects columns | Answers |
|---|---|---|
| `anytime(df, by=…)` | `t`, `score` | the best-so-far progress curve |
| `auc(curve)` | `t`, `best_so_far` | the anytime score (left-Riemann, span-normalized) |
| `scaling(df, by=…)` | `budget`, `reward` | score vs interaction budget (EdgeBench 2–12 h) |
| `improvements(df, by=…)` | `t`, `score` | evals vs strict improvements, and their ratio |
| `rescale_linear` / `rescale_anchored` | a Series | 0–100 normalization; anchored stretches past 100 beyond the best known result |

## The column contract

The store never fixes a result schema; instead **each metric documents the
columns it expects** and your script supplies them as tags. That is the
entire mechanism keeping free-form tags from becoming chaos.

Two more rules keep the numbers honest:

1. **Raw in the store, normalized in the view** — rescales apply at query
   time, so re-anchoring never requires re-running anything.
2. **Missing expectations are loud** — a degenerate input raises rather
   than silently returning half an answer.

## Add a metric

One pure function + a docstring declaring its expected columns + a
small-frame test (see `tests/test_metrics.py` — each is 5–10 lines).
There is no registry to update.
