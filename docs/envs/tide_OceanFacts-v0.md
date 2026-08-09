# tide/OceanFacts-v0

8-document ingest-then-probe stream; every phase re-asks all questions seen so far.

```python
import tide

env = tide.make("tide/OceanFacts-v0")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | dict: `phase`, `ingest` (the document to learn), `questions` (chat messages, cumulative) |
| **Action** | list[str]: one answer per question, in order |
| **Reward** | fraction of answers containing the expected fact (deterministic keyword judge) |
| **Source** | `tasks/streams/ocean-facts` |

Stream envs feed learning material phase by phase and measure what stuck.
Run two arms — memory kept across phases (stateful) vs wiped (fresh) — and
`tide.metrics.gain` isolates learning from capability. Judged offline and
deterministically; no API keys needed.

## Version history

- **v0** — initial release.
