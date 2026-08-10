# _template — copy this folder to make a task

```bash
cp -r tasks/_template tasks/autoresearch/my-task
```

Then work through the `TODO(task)` markers in each file:

1. `task.toml` — name, description, budget (`[agent] timeout_sec`)
2. `instruction.md` — the problem, the output format, the protocol
3. `environment/scorer.py` — the public (untrusted) scorer the agent iterates against
4. `tests/grade.py` — the trusted grader: recompute from the artifact, never trust claims
5. `tests/vectors.json` — the oracle's expected score + every cheat you can think of
6. `solution/solve.sh` — the oracle baseline (proves the task is solvable)

Run `pytest tests/test_task_suite.py` from the repo root — your folder is
picked up automatically: oracle score, cheat suite, and stock-Harbor
validation, no test code to write. Then prove it in containers:
`harbor trial start -p tasks/autoresearch/my-task`.

Full reference — the grader contract, the `vectors.json` schema (what a
cheat vector is), network policy, and GPU tasks:
[docs/components/tasks.md](../../docs/components/tasks.md).
