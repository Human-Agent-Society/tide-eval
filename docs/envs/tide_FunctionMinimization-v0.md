# tide/FunctionMinimization-v0

Minimize the deceptive Levi N.13 function.

```python
import tide

env = tide.make("tide/FunctionMinimization-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | dict: `instruction` (markdown) + `files` (the task's data files) |
| **Action** | a candidate solution object (the task's solution.json schema) |
| **Reward** | 1/(1+f(x,y)); global optimum scores 1.0, the origin scores 1/3. |
| **Source** | `tasks/autoresearch/function-minimization` |

Task envs score every `step` with the task's real grader, locally, no
containers — and track the best solution seen. `env.final()` re-grades the
best solution with the trusted grader (for held-out tasks, that is the number
to report). To evaluate a full agent in containers instead:
`tide run tasks/autoresearch/function-minimization --agent <name>`.

## Version history

- **v0** — initial release.
