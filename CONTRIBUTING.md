# Contributing to tide

Thanks for considering it. tide stays small on purpose, so contributions are
reviewed against a short list of design rules more than against style.

## The rules PRs are reviewed against

1. **One frozen surface.** `Lab.run`'s signature and the results-table schema
   don't change; columns may be added, never renamed or retyped. If your
   change needs to break this, open an issue first — it means the design is
   wrong somewhere and we'd rather fix that.
2. **Tasks stay stock Harbor.** No tide-specific fields in `task.toml`,
   ever. Stream/benchmark structure lives in manifests and scripts *around*
   tasks. `tests/test_harbor_integration.py` enforces this for the in-repo
   exemplar; new example tasks should extend that test.
3. **Abstractions are earned.** A helper enters the library when the same
   shape has appeared in at least two real scripts. Until then it lives in
   `examples/`. (This is why there is no stream "runner" class.)
4. **Dependency direction.** Converters/loaders depend on published formats
   and tide's public types only. Metrics import pandas, never tide. The core
   doesn't know streams exist.
5. **Trust boundaries are tested, not asserted.** Anything claiming to be an
   anti-hack measure needs a test that actually cheats and fails — see
   `tests/test_exemplar_grader.py` for the pattern.
6. **Loud beats lenient** for measurement code: a missing metric column, a
   duplicate store key, or a corrupt benchmark line raises; only
   agent-written data (score logs) is parsed leniently.

## What's welcome

- **Benchmark converters/loaders** (see the README catalog's 🗺️ rows —
  EdgeBench and AgentStream are the most wanted). A converter PR should
  include: the conversion script, one converted sample task checked in as a
  test fixture, and a catalog row update with honest status.
- **Metrics**: one pure function + docstring declaring expected columns +
  a small-frame test. That's the whole checklist.
- **Executors** for new backends, implementing the `Executor` protocol.
- **Example protocols** under `examples/` — real CL/autoresearch scripts are
  how library helpers get earned.

## Workflow

```bash
uv venv --python 3.12 && uv pip install -e . pytest pytest-asyncio ruff
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check . && .venv/bin/ruff format .
```

CI runs the tests, lint, and the offline examples on every PR. Harbor-
dependent tests skip when Harbor isn't installed; if your change touches the
Harbor mapping, install it locally (`uv pip install -e path/to/harbor`) and
run `tests/test_harbor_integration.py`.
