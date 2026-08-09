"""Trusted grader. Rules:

- recompute everything from the artifact; NEVER read agent-claimed scores;
- validate constraints conservatively (exact arithmetic where floats can be
  gamed; reject, don't round, on violations);
- reward.json is numbers-only; the human reason goes to reason.txt.
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
        solution = json.loads(Path(artifact).read_text())  # noqa: F841
    except (ValueError, TypeError) as e:
        return {"reward": 0.0, "reason": f"malformed solution: {e}"}
    raise NotImplementedError("TODO(task): validate + recompute the reward")


if __name__ == "__main__":
    result = grade(find_artifact())
    reason = result.pop("reason", "")
    REWARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REWARD_PATH.write_text(json.dumps(result))
    (REWARD_PATH.parent / "reason.txt").write_text(reason or "ok")
    print(json.dumps(result), reason)
