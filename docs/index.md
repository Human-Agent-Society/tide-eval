# tide

Evaluate agents that improve: on autoresearch tasks (open-ended
optimization problems with hours of budget, a continuous score, and an
agent iterating against a judge it cannot tamper with) and on
continual-learning task streams (ordered task sequences under one agent
that carries its memory from episode to episode).

- **[Get started](introduction/get-started.md)**: install to a real agent
  score, including auth and network setup.
- **[Design](introduction/design.md)**: the trust model, where the judge owns all
  scoring.
- **[Evaluating your agent](guides/integration.md)**: bring your own agent
  or method.
- **[Authoring tasks](guides/authoring-tasks.md)**: new tasks and benchmark
  converters.
- **API**: [lab](api/lab.md) · [streams](api/streams.md) ·
  [budget](api/budget.md) · [executors](api/executors.md) ·
  [metrics](api/metrics.md)

The [benchmark catalog](tasks/index.md): 6 first-party autoresearch tasks,
plus EdgeBench (51) and FrontierCS (208) converted to the same format.
