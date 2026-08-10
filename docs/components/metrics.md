# Metrics

`tide/metrics.py` — pure functions, `DataFrame in → DataFrame/Series out`.
They import pandas and nothing else from tide, so they work on any exported
results table (including one you didn't produce).

## The tag-hygiene contract

The store never fixes a schema; instead **each metric documents the columns
it expects**, and your script supplies those tags. This is the whole
mechanism keeping free-form tags from becoming chaos — when writing a new
metric, state its required columns in the docstring first.

| Function | Expects columns | Answers |
|---|---|---|
| `anytime(df, by=…)` | `t`, `score` (+groups) | best-so-far progress curve |
| `auc(curve)` | `t`, `best_so_far` | the anytime score (left-Riemann, span-normalized) |
| `scaling(df)` | `budget`, `reward` | score vs interaction budget (EdgeBench 2–12 h) |
| `improvements(df, by=…)` | `t`, `score` (+groups) | evals vs strict improvements, and their ratio |
| `rescale_linear` / `rescale_anchored` | a Series | 0–100 normalization; anchored stretches >100 past the best known result |

## Rules

1. **Raw in the store, normalized in the view.** Rescales are applied at
   query time so re-anchoring never requires re-running anything.
2. **Missing expectations are loud** — `rescale_linear` raises on a
   degenerate anchor rather than silently returning half an answer. Keep
   that style.
3. Aggregation over repeats is `mean` unless a metric says otherwise.

## How to modify

Add a function. Document its expected columns. Add a test with a tiny
hand-built frame (see `tests/test_metrics.py` — each metric is 5–10 lines to
test). That's the entire process; there is no registry to update.
