# tide/CirclePacking-v0

Pack 3 circles in the unit square, maximize the sum of radii.

```python
import tide

env = tide.make("tide/CirclePacking-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | dict: `instruction` (markdown) + `files` (the task's data files) |
| **Action** | a candidate solution object (the task's solution.json schema) |
| **Reward** | sum of radii; 0 for any constraint violation (exact arithmetic). Oracle 0.75, optimum ≈1.0076. |
| **Source** | `tasks/autoresearch/circle-packing` |

Task envs score every `step` with the task's real grader, locally, no
containers — and track the best solution seen. `env.final()` re-grades the
best solution with the trusted grader (for held-out tasks, that is the number
to report). To evaluate a full agent in containers instead:
`tide run tasks/autoresearch/circle-packing --agent <name>`.

## Version history

- **v0** — initial release.
