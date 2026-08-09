# tide/BinPacking-v0

Pack 60 items into as few capacity-100 bins as possible.

```python
import tide

env = tide.make("tide/BinPacking-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | dict: `instruction` (markdown) + `files` (the task's data files) |
| **Action** | a candidate solution object (the task's solution.json schema) |
| **Reward** | first-fit bins / yours; 1.0 = first-fit; any constraint violation = 0. |
| **Source** | `tasks/autoresearch/bin-packing` |

Task envs score every `step` with the task's real grader, locally, no
containers — and track the best solution seen. `env.final()` re-grades the
best solution with the trusted grader (for held-out tasks, that is the number
to report). To evaluate a full agent in containers instead:
`tide run tasks/autoresearch/bin-packing --agent <name>`.

## Version history

- **v0** — initial release.
