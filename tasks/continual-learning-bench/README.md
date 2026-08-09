# Continual Learning Bench (arXiv 2606.05661)

The expert-built continual-learning benchmark from
[pgasawa/continual-learning-bench](https://github.com/pgasawa/continual-learning-bench)
(Apache-2.0): six task families — exploitable poker, sales prediction,
codebase adaptation, database exploration, cohort studies, blind spectrum
monitoring — where episodes share a learnable latent structure and a gain
metric isolates learning from capability.

Their tasks are **interactive Python simulations** (e.g. per-hand poker
against opponent policies), run by their own harness — not convertible to
static task dirs, and carrying a training-corpora canary, so nothing is
vendored here. Two supported workflows:

**1. Analyze their runs with tide** (works immediately — their repo ships
the full leaderboard results):

```bash
python tasks/continual-learning-bench/fetch.py     # clones their repo locally
```
```python
from tide.loaders import load_clbench_results
from tide import metrics

df = load_clbench_results("tasks/continual-learning-bench/repo/final_results/runs")
# 16,904 instance outcomes · 6 systems · 6 tasks, one row each
df.groupby(["system", "task"])["reward"].mean()  # the leaderboard
metrics.anytime(
    df, time="instance_index", score="reward", by=["system", "task"]
)  # learning curves
```

**2. Run their harness** to produce new results (Docker + model keys):

```bash
cd tasks/continual-learning-bench/repo
uv sync --all-extras && clbench setup --all
clbench run exploitable_poker --schedule quick_test --system icl
```

Their run outputs load with the same `load_clbench_results` call. For an
offline, first-party instance of the same protocol shape, see
[`tasks/streams/hidden-rules/`](../streams/hidden-rules).
