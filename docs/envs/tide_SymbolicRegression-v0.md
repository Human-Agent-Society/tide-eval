# tide/SymbolicRegression-v0

Recover a hidden formula from noiseless samples.

```python
import tide

env = tide.make("tide/SymbolicRegression-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | dict: `instruction` (markdown) + `files` (the task's data files) |
| **Action** | a candidate solution object (the task's solution.json schema) |
| **Reward** | steps: 1/(1+RMSE) on TRAIN points; final(): on HELD-OUT points — the anti-overfitting wall. |
| **Source** | `tasks/autoresearch/symbolic-regression` |

Task envs score every `step` with the task's real grader, locally, no
containers — and track the best solution seen. `env.final()` re-grades the
best solution with the trusted grader (for held-out tasks, that is the number
to report). To evaluate a full agent in containers instead:
`tide run tasks/autoresearch/symbolic-regression --agent <name>`.

## Version history

- **v0** — initial release.
