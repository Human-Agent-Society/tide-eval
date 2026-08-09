"""Trusted grader: recomputes 1/(1+f) from the artifact alone."""

import json
import math
from pathlib import Path

REWARD_PATH = Path("/logs/verifier/reward.json")
BOUND = 100.0  # |x|, |y| must be sane; unboundedly large inputs are rejected


def f(x: float, y: float) -> float:
    return (
        math.sin(3 * math.pi * x) ** 2
        + (x - 1) ** 2 * (1 + math.sin(3 * math.pi * y) ** 2)
        + (y - 1) ** 2 * (1 + math.sin(2 * math.pi * y) ** 2)
    )


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
        point = json.loads(Path(artifact).read_text())
        x, y = float(point["x"]), float(point["y"])
    except (KeyError, ValueError, TypeError) as e:
        return {"reward": 0.0, "reason": f"malformed solution: {e}"}
    if not (math.isfinite(x) and math.isfinite(y)):
        return {"reward": 0.0, "reason": "non-finite coordinates"}
    if abs(x) > BOUND or abs(y) > BOUND:
        return {"reward": 0.0, "reason": f"coordinates outside |v| <= {BOUND}"}
    value = f(x, y)
    return {"reward": 1.0 / (1.0 + value), "f": value}


if __name__ == "__main__":
    result = grade(find_artifact())
    reason = result.pop("reason", "")
    REWARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REWARD_PATH.write_text(json.dumps(result))
    (REWARD_PATH.parent / "reason.txt").write_text(reason or "ok")
    print(json.dumps(result), reason)
