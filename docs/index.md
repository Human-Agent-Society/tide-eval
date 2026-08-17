# tide

Evaluate learning from inference-time signals: feedback produced during
the run itself, with no training step in between. Autoresearch measures
a solution improving against an evaluator on one open-ended problem;
continual learning measures an agent carrying what it learned into the
next task.

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
