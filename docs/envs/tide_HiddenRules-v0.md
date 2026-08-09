# tide/HiddenRules-v0

Infer a hidden linear rule across 6 phases; accumulating observations should widen the gain.

```python
import tide

env = tide.make("tide/HiddenRules-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | dict: `phase`, `ingest` (this phase's observed rounds), `questions` (the query block) |
| **Action** | list[str]: one response containing 'Round n: WIN/LOSS' lines |
| **Reward** | fraction of query rounds labeled correctly (deterministic exact-line judge) |
| **Source** | `tasks/streams/hidden-rules` |

Stream envs feed learning material phase by phase and measure what stuck.
Run two arms — memory kept across phases (stateful) vs wiped (fresh) — and
`tide.metrics.gain` isolates learning from capability. Judged offline and
deterministically; no API keys needed.

## Version history

- **v0** — initial release.
