# tide

Evaluate agents on autoresearch tasks: open-ended optimization problems with
hours of budget, a continuous score, and an agent iterating against a judge
it cannot tamper with.

- **[Get started](get-started.md)** — install to a real agent score,
  including auth and network gotchas.
- **[Design](design.md)** — the trust model: the judge owns all scoring.
- **[Integration](integration.md)** — bring your own agent or method.
- **Components** — [tasks](components/tasks.md) · [lab](components/lab.md) ·
  [executors](components/executors.md) · [metrics](components/metrics.md)

The benchmark catalog lives in
[`tasks/`](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks):
6 first-party autoresearch tasks, plus EdgeBench (51) and FrontierCS (208)
converted to the same format.
