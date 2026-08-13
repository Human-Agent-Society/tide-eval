# Contributing to tide

Thanks for considering it. tide stays small on purpose, so contributions are
reviewed against a short list of design rules more than against style.

## The rules PRs are reviewed against

1. **One frozen interface.** `Lab.run`'s signature and the results-table schema
   don't change; columns may be added, never renamed or retyped. If your
   change needs to break this, open an issue first — it means the design is
   wrong somewhere and we'd rather fix that.
2. **Tasks stay stock Harbor.** No tide-specific fields in `task.toml`,
   ever. Benchmark structure lives in scripts *around* tasks.
   `tests/test_task_suite.py` enforces this for every committed task.
3. **Abstractions are earned.** A helper enters the library when the same
   shape has appeared in at least two real scripts. Until then it lives in
   `examples/`.
4. **Dependency direction.** Catalog conversion scripts depend on published
   formats, never tide's runtime internals. Metrics import pandas, never tide.
5. **Trust boundaries are tested, not asserted.** Anything claiming to be an
   anti-cheating measure needs a test that actually cheats and fails — see
   the cheat cases in `tests/test_task_suite.py` for the pattern.
6. **Loud beats lenient** for measurement code: a missing metric column, a
   duplicate store key, or a corrupt benchmark line raises. Only submitted
   solutions are handled leniently — they score 0 with a reason instead of
   raising.
7. **The two READMEs move together.** A PR that changes `README.md` updates
   `README_CN.md` in the same commit.
8. **Unbuilt work lives in the roadmap.** Docs state what exists; where a
   gap must be mentioned, link the [roadmap issue](https://github.com/Human-Agent-Society/tide-eval/issues/19)
   instead of writing "not built yet" in place.

## What's welcome

- **Autoresearch tasks** — copy `tasks/_template`, work the TODO markers,
  and `tests/test_task_suite.py` picks it up (oracle score, cheat suite,
  stock-Harbor validation) with zero test code written.
- **Benchmark converters**. A converter PR should include: the conversion
  script, one converted sample task checked in as a test fixture, and a
  catalog row update with honest status.
- **Metrics**: one pure function + docstring declaring expected columns +
  a small-frame test. That's the whole checklist.
- **Executors** for new backends, implementing the `Executor` protocol.
- **Example protocols** under `examples/` — real autoresearch scripts are
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
