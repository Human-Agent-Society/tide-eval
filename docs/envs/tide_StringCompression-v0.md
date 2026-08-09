# tide/StringCompression-v0

Ship a decompressor + payload that reproduces the corpus byte-exactly.

```python
import tide

env = tide.make("tide/StringCompression-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | dict: `instruction` (markdown) + `files` (the task's data files) |
| **Action** | a candidate solution object (the task's solution.json schema) |
| **Reward** | corpus bytes / compressed bytes (zlib ≈3.47); failed round trip = 0. Decompressor runs sandboxed, ≤15s. |
| **Source** | `tasks/autoresearch/string-compression` |

Task envs score every `step` with the task's real grader, locally, no
containers — and track the best solution seen. `env.final()` re-grades the
best solution with the trusted grader (for held-out tasks, that is the number
to report). To evaluate a full agent in containers instead:
`tide run tasks/autoresearch/string-compression --agent <name>`.

## Version history

- **v0** — initial release.
