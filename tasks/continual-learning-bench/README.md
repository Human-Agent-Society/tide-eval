# Continual Learning Bench (arXiv 2606.05661)

The expert-built continual-learning benchmark from
[pgasawa/continual-learning-bench](https://github.com/pgasawa/continual-learning-bench)
(Apache-2.0): six task families — exploitable poker, sales prediction,
codebase adaptation, database exploration, cohort studies, blind spectrum
monitoring — where episodes share a **learnable latent structure** (opponent
strategies, codebase layout, outbreak dynamics), and a **gain metric** that
isolates learning from raw capability.

## Using it today

Their harness is self-contained (own CLI, own containers, own schedules) and
runs directly:

```bash
git clone https://github.com/pgasawa/continual-learning-bench && cd continual-learning-bench
uv sync --all-extras && clbench setup --all
clbench run exploitable_poker --schedule quick_test --system icl
```

## How it maps onto tide

Their concepts land exactly on tide's primitives — each episode in a task
sequence is a tide **episode**; a schedule is a **stream**; their gain metric
is `metrics.gain` (stateful vs fresh arms); their improvement-over-episodes
reward is `metrics.matrix` sliced by phase. What's not built yet is the
converter (their tasks → Harbor task dirs + a stream manifest) — tracked on
the [roadmap](../../README.md#roadmap). Until then:

- run their harness as-is for their leaderboard numbers;
- use [`tasks/streams/hidden-rules/`](../streams/hidden-rules) — an offline
  first-party instance of the same protocol shape — to develop and test your
  learner loop in tide before spending on the real thing.
