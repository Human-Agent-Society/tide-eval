# Metrics

`tide/metrics.py`: pure functions, `DataFrame in → DataFrame/Series out`.
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
metrics.learning_curve(ep, by=["stream"])  # score over stream position
```

Autoresearch curves, over trace rows:

| Function | Expects columns | Answers |
|---|---|---|
| `anytime(df, by=…)` | `t`, `score` | the best-so-far progress curve |
| `auc(curve)` | `t`, `best_so_far` | the anytime score: area under the best-so-far curve ÷ time span |
| `time_to(df, threshold, by=…)` | `t`, `score` | how long until the score first reached a threshold (NaN if never) |
| `improvements(df, by=…)` | `t`, `score` | evals vs strict improvements, and their ratio |

Budgets, over episode rows:

| Function | Expects columns | Answers |
|---|---|---|
| `scaling(df, budget=…, by=…)` | *budget col*, `reward` | score vs budget on any axis; pass `budget="budget_max_tokens"`, `"budget"` (hours), … |
| `efficiency(df, spend=…, per=…, by=…)` | a `used_*` col, `reward` | reward per unit actually spent (per 1k tokens, per dollar, per eval); see [budget](budget.md) |

Streams, over episode rows tagged `stream` and `position` (see
[streams](streams.md)):

| Function | Expects columns | Answers |
|---|---|---|
| `learning_curve(df, by=…)` | `position`, `reward` | score over stream position, with `cum_mean` and optional `rolling_mean` |
| `transfer(stream_df, baseline_df)` | `task`, `reward` in both | stream performance vs the same tasks run isolated |
| `forgetting(df)` | `task`, `position`, `reward` | how much revisited tasks degraded |

Normalizers:

| Function | Expects | Answers |
|---|---|---|
| `rescale_linear` / `rescale_anchored` | a Series | 0-100 normalization; anchored stretches past 100 beyond the best known result |

## The column contract

The store never fixes a result schema; instead **each metric documents the
columns it expects** and your script supplies them as tags. That is what
keeps free-form tags consistent across scripts.

Two more rules keep the numbers comparable:

1. **Raw in the store, normalized in the view**: rescales apply at query
   time, so re-anchoring never requires re-running anything.
2. **Missing expectations are loud**: a degenerate input raises rather
   than silently returning half an answer.

## Add a metric

One pure function + a docstring declaring its expected columns + a
small-frame test (see `tests/test_metrics.py`; each is 5-10 lines).
There is no registry to update.
