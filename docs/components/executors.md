# Executors

`tide/executors.py` — an executor turns an `EpisodeSpec` into an
`EpisodeResult`. This one seam is why the core is testable without Docker
and why new backends never touch the Lab.

## The contract

```python
class Executor(Protocol):
    async def execute(self, spec: EpisodeSpec) -> EpisodeResult: ...
```

`EpisodeSpec` = `(task, agent, overrides)` · `EpisodeResult` =
`(rewards, uri, trace, error)`. Three rules:

1. **Return, don't raise, on task-level failure.** A timeout or agent crash
   is a *result* (`error=…`, possibly empty rewards) — the episode row must
   still be written so the sweep continues. Raise only for infrastructure
   bugs.
2. **`rewards` must be trusted** by the backend's own standard (Harbor: the
   isolated verifier). Untrusted numbers belong in `trace`.
3. **`uri` must make the result auditable** — point it at logs/artifacts.

## Shipped

- **`HarborExecutor(trials_dir)`** — the benchmark run. Builds a
  `TrialConfig` (the agent dict passes to Harbor's `AgentConfig` verbatim;
  `overrides` onto `TrialConfig` fields), runs the trial with the judge as
  a sidecar, ingests the judge's submission log into `trace`. Harbor is imported
  lazily, so the rest of tide works without it installed.
- **`LocalExecutor(root=…)`** — the development run: starts the task's own
  `judge_server.py` as a local process, runs your `command` with
  `$JUDGE_URL` and `$BUDGET_SEC` set, and takes the judge's final verdict.
  The same judge code as containers, no Docker — rows carry a `local://`
  uri because the judge ran on a machine the agent also controls.
- **`FakeExecutor(score=…, trace=…)`** — deterministic and instant; powers
  the test suite, `--fake`, and the offline examples. Records `calls` for
  assertions.

## Extend it

A new backend (SSH box, cloud batch API, a simulator) is a class in *your*
code implementing the protocol — `Lab(root, executor=YourExecutor())` and
nothing in tide needs to know:

```python
class SSHExecutor:
    async def execute(
        self, spec
    ): ...  # run the task remotely, return EpisodeResult(rewards=..., uri=...)
```

For different Harbor wiring (custom verifier env, extra mounts), prefer
passing `TrialConfig` fields through `lab.run(..., verifier={...})` — the
executor forwards `overrides` untouched. When bumping the Harbor pin, run
`tests/test_harbor_integration.py` first: it pins the config mapping.
