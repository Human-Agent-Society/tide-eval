# terminal-bench — the continual-learning stream benchmark

**What**: [terminal-bench 2.0](https://github.com/laude-institute/terminal-bench-2)
— 89 pass/fail terminal tasks (build a project, fix a repo, drive a CLI),
each a stock Harbor task with its own container and verifier. A pass is
reward 1.0, a fail 0.0, so the stream metrics (`learning_curve`,
`transfer`, `forgetting`) work on it directly.

**Version**: 2.0 only. The pin in [`fetch.py`](fetch.py) is the exact
commit the Harbor registry publishes as v2.0; terminal-bench 1.x predates
the Harbor task format and is deliberately not supported.

**License**: Apache-2.0 (upstream). **All 89 tasks are committed here**,
so they run out of the box; [`fetch.py`](fetch.py) re-syncs them from the
pinned commit if you ever need to regenerate:

```bash
tide stream my-stream terminal-bench --agent claude-code --model anthropic/claude-opus-5
```

The stream runs the tasks in name order with the agent's memory directory
(`$TIDE_STATE_DIR`) carried from task to task. For a custom order, a
subset, or repeats (how forgetting is measured), list the task folders
yourself:

```bash
tide stream my-stream terminal-bench/chess-best-move terminal-bench/build-pmars \
  terminal-bench/chess-best-move --agent claude-code --model anthropic/claude-opus-5
```

The isolated control arm for `metrics.transfer` is a plain run over the
same tasks: `tide run terminal-bench/<task> --agent <a>`.
