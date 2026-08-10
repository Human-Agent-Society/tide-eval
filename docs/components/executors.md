# Executors

`tide/executors.py` — an executor turns an `EpisodeSpec` into an
`EpisodeResult`. This indirection is why the core is testable without Docker
and why new backends never touch the Lab.

## The contract

```python
class Executor(Protocol):
    async def execute(self, spec: EpisodeSpec) -> EpisodeResult: ...
```

`EpisodeSpec` = `(task, agent, overrides)`; `EpisodeResult` =
`(rewards, uri, trace, error)`. Rules an executor must honor:

1. **Return, don't raise, on task-level failure.** A timeout or agent crash
   is a *result* (`error=…`, possibly empty rewards) — the episode row must
   still be written so the sweep can continue. Raise only for
   infrastructure bugs.
2. **`rewards` must be trusted** by whatever standard the backend has
   (Harbor: the verifier). Untrusted numbers belong in `trace`.
3. **`uri` must make the result auditable** — point at logs/artifacts.

## Shipped executors

- **`HarborExecutor(trials_dir)`** — builds a `TrialConfig`
  (agent dict passes through to Harbor's `AgentConfig` verbatim; `overrides`
  onto `TrialConfig` fields), runs `Trial.create/run`, ingests
  `score_log.jsonl` from the trial's artifacts into `trace`. Harbor is
  imported lazily — the rest of tide works without it installed.
- **`FakeExecutor(score=…, trace=…)`** — deterministic and instant; the test
  suite and offline examples run on it. Records `calls` for assertions.

## How to modify

- **New backend** (SSH box, cloud batch API, a simulator): implement the
  protocol in your own module and pass `Lab(root, executor=YourExecutor())`.
  Nothing in tide needs to know.
- **Different Harbor wiring** (custom verifier env, extra mounts): prefer
  passing `TrialConfig` fields through `lab.run(..., verifier={...},
  environment={...})` — the executor forwards `overrides` untouched. Only
  subclass `HarborExecutor` if you need to post-process results.
- **Version bumps**: Harbor's model API moves; `tests/test_harbor_integration.py`
  pins the mapping (config assembly + the exemplar task validating against
  `TaskConfig`). Run it against a new Harbor before upgrading the pin.
