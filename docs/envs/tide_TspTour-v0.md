# tide/TspTour-v0

Find a short closed tour over 40 fixed cities.

```python
import tide

env = tide.make("tide/TspTour-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | dict: `instruction` (markdown) + `files` (the task's data files) |
| **Action** | a candidate solution object (the task's solution.json schema) |
| **Reward** | identity-tour length / yours; 1.0 = file order, ~2.0 = strong heuristics; invalid permutation = 0. |
| **Source** | `tasks/autoresearch/tsp-tour` |

Task envs score every `step` with the task's real grader, locally, no
containers — and track the best solution seen. `env.final()` re-grades the
best solution with the trusted grader (for held-out tasks, that is the number
to report). To evaluate a full agent in containers instead:
`tide run tasks/autoresearch/tsp-tour --agent <name>`.

## Version history

- **v0** — initial release.
