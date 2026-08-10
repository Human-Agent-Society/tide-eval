# Continual Learning Bench (arXiv 2606.05661)

The expert-built continual-learning benchmark from
[pgasawa/continual-learning-bench](https://github.com/pgasawa/continual-learning-bench)
(Apache-2.0): six task families — exploitable poker, sales prediction,
codebase adaptation, database exploration, cohort studies, blind spectrum
monitoring — where episodes share a learnable latent structure and a gain
metric isolates learning from capability.

Their tasks are **interactive Python simulations** (per-hand poker against
opponent policies, and five more families). tide brings them in without
copying a line of their code: the container pip-installs their package at a
pinned commit and drives their own task classes. Three workflows:

**0. Run a CLB task as a Harbor task** — [`exploitable-poker/`](exploitable-poker)
is fully converted: the agent plays their unmodified 120-hand default schedule
through a file bridge, and grading **replays the action log** against the same
deterministic task in a clean container (locally proven: check/call oracle
scores exactly -0.15; forged logs change nothing):

```bash
tide run tasks/continual-learning-bench/exploitable-poker --agent claude-code --model ...
```

The same bridge pattern extends to the other five families (roadmap).

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

**2. Run it through tide** (their harness underneath; Docker + model keys;
one-time setup: `cd repo && uv sync --all-extras && clbench setup --all`):

```bash
python tasks/continual-learning-bench/run.py exploitable_poker \
    --system icl --schedule quick_test --lab runs/clbench
tide report --lab runs/clbench --kind external
```

The wrapper runs `clbench run` and ingests every instance outcome into the
tide store (kind `external`, tagged system/model/task/instance), so their
results and your tide runs live in one queryable place. For an
offline, first-party instance of the same protocol shape, see
[`tasks/streams/hidden-rules/`](../streams/hidden-rules).
