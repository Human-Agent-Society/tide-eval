# tasks/ — the benchmark catalog

One folder per benchmark. A folder contains either ready-to-run Harbor task
directories (vendored when the license allows), or a `fetch.py` that
materializes them in place from the upstream source. Either way, every task
that ends up here is a stock Harbor task: run it with
`lab.run("tasks/<benchmark>/<task>", agent)` or standalone with
`harbor trial start -p <dir>`.

| Folder | What's inside | How to get the tasks |
|---|---|---|
| [`circle-packing-mini/`](circle-packing-mini) | tide's reference autoresearch task (dual scorer, separate verifier, budget semantics) | vendored — ready to run |
| [`frontier-cs/`](frontier-cs) | FrontierCS 2.0 (240 open CS problems; MIT). One task vendored as a working sample | `python tasks/frontier-cs/fetch.py` generates more via their official adapter |
| [`edgebench/`](edgebench) | EdgeBench (51 tasks, 2–12 h budgets, ByteDance-Seed) | `python tasks/edgebench/fetch.py <task_id>` converts specs from HuggingFace |
| [`clbench/`](clbench) | Tencent CL-bench / CL-bench Life (2,300+ rubric-judged probes; their license — not redistributed) | `python tasks/clbench/fetch.py` downloads the JSONL; load with `tide.loaders` |

**Defining a new task**: copy the layout of `circle-packing-mini/`
(`task.toml · instruction.md · environment/ · tests/ · solution/`), then read
[docs/components/tasks.md](../docs/components/tasks.md) for the autoresearch
conventions (anti-hack wall, budget semantics, score logs) and the
oracle/nop/cheater checklist. Verify with `harbor trial start -p <dir>` —
tasks here must always remain valid stock Harbor tasks.

**Adding a new benchmark**: add a folder with a README (what/license/count)
plus either vendored task dirs or a `fetch.py`. Converters that parse a
published spec format belong in `tide/converters/` with fixture tests;
the folder's `fetch.py` is just the user-facing entry that calls them.
