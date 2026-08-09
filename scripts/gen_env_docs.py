"""Generate Gym-style doc pages for every registered env → docs/envs/.

    python scripts/gen_env_docs.py

Pages are rendered from the registry's EnvSpec doc fields, so registration
is the single source of truth (edit registrations.py, re-run this).
"""

from pathlib import Path

import tide

OUT = Path(__file__).parent.parent / "docs" / "envs"

PAGE = """# {id}

{description}

```python
import tide

env = tide.make("{id}")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
```

| | |
|---|---|
| **Observation** | {observation_doc} |
| **Action** | {action_doc} |
| **Reward** | {reward_doc} |
| **Source** | `tasks/{source}` |

{extra}

## Version history

- **v0** — initial release.
"""

TASK_EXTRA = """Task envs score every `step` with the task's real grader, locally, no
containers — and track the best solution seen. `env.final()` re-grades the
best solution with the trusted grader (for held-out tasks, that is the number
to report). To evaluate a full agent in containers instead:
`tide run tasks/{source} --agent <name>`."""

STREAM_EXTRA = """Stream envs feed learning material phase by phase and measure what stuck.
Run two arms — memory kept across phases (stateful) vs wiped (fresh) — and
`tide.metrics.gain` isolates learning from capability. Judged offline and
deterministically; no API keys needed."""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = ["# Environments\n"]
    for env_id in tide.envs.registry.all_ids():
        spec = tide.envs.registry.spec(env_id)
        source = spec.kwargs.get("relative", "")
        extra = (
            STREAM_EXTRA if "streams/" in source else TASK_EXTRA.format(source=source)
        )
        page = PAGE.format(
            id=spec.id,
            description=spec.description,
            observation_doc=spec.observation_doc,
            action_doc=spec.action_doc,
            reward_doc=spec.reward_doc,
            source=source,
            extra=extra,
        )
        filename = spec.id.replace("/", "_") + ".md"
        (OUT / filename).write_text(page)
        index.append(f"- [`{spec.id}`]({filename}) — {spec.description}")
    (OUT / "README.md").write_text("\n".join(index) + "\n")
    print(f"wrote {len(tide.envs.registry.all_ids())} env pages to {OUT}")


if __name__ == "__main__":
    main()
