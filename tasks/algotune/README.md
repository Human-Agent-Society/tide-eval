# AlgoTune

154 "speed up this code" tasks from
[oripress/AlgoTune](https://github.com/oripress/AlgoTune): each gives a
reference implementation and rewards beating its runtime — continuous
scores, exactly the autoresearch shape.

There is no vendored folder here because these tasks come straight from
the [Harbor registry](https://github.com/laude-institute/harbor/tree/main/adapters/algotune):
Harbor downloads a task by id the first time you run it.

```bash
tide run algotune/psd_cone_projection --agent claude-code --model anthropic/claude-opus-5
```

```python
await lab.run("algotune/psd_cone_projection", agent={...})
```

What tide adds on top of running these through Harbor directly: the
shared results table, resume, budget tags, and cross-agent comparison.
What it can't add yet: the trusted score-over-time curve — these tasks
predate the judge protocol, so each run yields one final score and no
submission log. A judge-protocol conversion would close that gap.

Task list and licensing: see the upstream repo and the Harbor adapter.
