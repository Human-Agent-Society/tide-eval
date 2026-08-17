# Tasks

The benchmark catalog: six first-party autoresearch tasks, plus external
benchmarks converted to the same Harbor task format. Every task is a stock
Harbor task, so it runs two ways, always:

```bash
tide run autoresearch/first-party/tsp-tour --agent oracle      # through tide
harbor trial start -p tasks/autoresearch/first-party/tsp-tour  # stock Harbor, standalone
```

`tide list` shows everything runnable. To author your own, start from
[`tasks/_template`](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/_template)
and follow [Authoring tasks & benchmarks](../guides/authoring-tasks.md).

## Autoresearch

First-party, offline, oracle-verified in CI (real containers). Each task
teaches one hard part of the category.

| Task | One line | Oracle → best known | Teaches |
|---|---|---|---|
| [`circle-packing`](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/first-party/circle-packing) | pack 3 circles, maximize Σ radii | 0.75 → 1.0076 | the full protocol, exact-arithmetic grading |
| [`function-minimization`](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/first-party/function-minimization) | minimize deceptive Levi N.13 | 0.333 → 1.0 | exploration vs local search |
| [`tsp-tour`](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/first-party/tsp-tour) | shorten a 40-city tour | 1.0 → ~2.0 | combinatorial search, continuous signal |
| [`bin-packing`](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/first-party/bin-packing) | beat first-fit on 60 items | 1.0 → >1.0 | exact constraint checking |
| [`symbolic-regression`](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/first-party/symbolic-regression) | recover a hidden formula | 0.604 → 1.0 | **held-out grading**: scored on points the agent never saw |
| [`string-compression`](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/first-party/string-compression) | ship decompressor + payload | 3.47 → higher | **grading agent-shipped code safely** |

```bash
tide run autoresearch/first-party --agent oracle   # the whole suite
```

## External benchmarks

Converted to the same task format and committed to the repo; each suite's
`fetch.py` / `convert.py` regenerates it from the published sources.

| Suite | Tasks | Run |
|---|---|---|
| [EdgeBench](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/edgebench) ([upstream](https://github.com/ByteDance-Seed/EdgeBench), CC-BY-4.0) | 51 · 2-12 h budgets | `tide run edgebench/<task> --budget <h>` |
| [FrontierCS](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/frontier-cs) ([upstream](https://github.com/FrontierCS/Frontier-CS), MIT) | 188 algorithmic + 20 research · incl. 4 GPU kernel | `tide run frontier-cs/<task> --agent <a>` |
