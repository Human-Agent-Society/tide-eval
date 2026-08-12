# tide

Evaluate agents on autoresearch tasks: open-ended optimization problems with
hours of budget, a continuous score, and an agent iterating against a judge
it cannot tamper with.

- **[Get started](introduction/get-started.md)** — install to a real agent
  score, including auth and network gotchas.
- **[Design](introduction/design.md)** — the trust model: the judge owns all
  scoring.
- **[Evaluating your agent](guides/integration.md)** — bring your own agent
  or method.
- **[Authoring tasks](guides/authoring-tasks.md)** — new tasks and benchmark
  converters.
- **API** — [lab](api/lab.md) · [budget](api/budget.md) ·
  [executors](api/executors.md) · [metrics](api/metrics.md)

The [benchmark catalog](tasks/index.md): 6 first-party autoresearch tasks,
plus EdgeBench (51) and FrontierCS (208) converted to the same format.
