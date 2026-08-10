# _template — copy this folder to make a task

The template **is a complete working task** (maximize `x` in `[0, 1]`) —
the test suite is green the moment you copy it. Replace one piece at a
time and keep the suite green:

```bash
cp -r tasks/_template tasks/autoresearch/my-task
pytest tests/test_task_suite.py            # your copy is picked up automatically
```

Work through the `TODO(task)` markers:

1. `task.toml` — name, description, budget (`[agent] timeout_sec`)
2. `instruction.md` — the problem, the output format, the protocol
3. `environment/scorer.py` — the public scorer the agent iterates against
4. `tests/grade.py` — the private grader: recompute from the artifact, never trust claims
5. `tests/grader_tests.json` — the oracle's expected reward + every cheat you can think of
6. `solution/solve.sh` — the oracle baseline (proves the task is solvable)

Then prove it in containers: `harbor trial start -p tasks/autoresearch/my-task`.

## One scoring rule, two implementations — on purpose

You write the scoring **twice**: once in `environment/scorer.py` (public,
agent-facing) and once in `tests/grade.py` (private, trusted). This is a
deliberate design, not an oversight:

- the two files live in **different build contexts** (`environment/` builds
  the agent image, `tests/` builds the verifier image), so they physically
  cannot import each other;
- the private side should usually be **stricter** anyway — exact arithmetic
  where floats can be gamed, held-out data, conservative rejection. In this
  template the public scorer tolerates `1e-9` while the private grader
  rejects `x > 1` exactly; the `epsilon_over` cheat case pins that gap.

If your two implementations drift apart, scores stay correct — the public
side only misleads the agent's own search. Prefer single-source anyway?
Keep the shared function in `tests/` and copy it into `environment/`
yourself; the default is duplication because the private side usually
diverges on purpose.

Full reference — the grader contract, the `grader_tests.json` schema (what a
cheat case is), network policy, and GPU tasks:
[docs/components/tasks.md](../../docs/components/tasks.md).
