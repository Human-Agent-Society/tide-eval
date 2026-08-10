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

Task list and licensing: see the upstream repo and the Harbor adapter.
