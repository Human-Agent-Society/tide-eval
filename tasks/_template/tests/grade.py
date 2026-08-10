"""Trusted grader. Rules:

- recompute everything from the artifact; NEVER read agent-claimed scores;
- validate conservatively (exact arithmetic where floats can be gamed;
  reject, don't round, on violations);
- reward.json is numbers-only; the human reason goes to reason.txt.

Written separately from environment/scorer.py ON PURPOSE — the two files
live in different build contexts and the private side is stricter (this one
rejects x > 1 exactly; the public scorer tolerates 1e-9 — the epsilon case
in grader_tests.json pins that gap).

TODO(task): replace the checks in grade() with your task's.
"""

import json
from pathlib import Path

REWARD_PATH = Path("/logs/verifier/reward.json")


def find_artifact() -> Path | None:
    canonical = Path("/app/best/solution.json")
    if canonical.exists():
        return canonical
    hits = sorted(Path("/logs/artifacts").rglob("solution.json"))
    return hits[0] if hits else None


def grade(artifact: Path | None) -> dict:
    if artifact is None or not Path(artifact).exists():
        return {"reward": 0.0, "reason": "no solution.json artifact"}
    try:
        solution = json.loads(Path(artifact).read_text())
        x = float(solution["x"])
    except (ValueError, TypeError, KeyError) as e:
        return {"reward": 0.0, "reason": f"malformed solution: {e!r}"}
    if not 0.0 <= x <= 1.0:  # exact bounds — stricter than the public scorer
        return {"reward": 0.0, "reason": f"x={x} outside [0, 1]"}
    return {"reward": x, "reason": "ok"}


if __name__ == "__main__":
    result = grade(find_artifact())
    reason = result.pop("reason", "")
    REWARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REWARD_PATH.write_text(json.dumps(result))
    (REWARD_PATH.parent / "reason.txt").write_text(reason or "ok")
    print(json.dumps(result), reason)
