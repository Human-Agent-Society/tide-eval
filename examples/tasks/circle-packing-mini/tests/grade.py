"""Trusted grader: recomputes the score from the declared artifact, from
scratch, in exact rational arithmetic.

Never reads the agent's claimed scores. Runs in a separate verifier container
that received only the declared artifacts, so nothing the agent did to its own
environment (including tampering with the public scorer) can reach this code.

Conservative by construction: exact Fraction comparisons with the documented
1e-9 tolerance, so buying radius with float-epsilon overlaps scores zero.
"""

import json
from fractions import Fraction
from pathlib import Path

OPTIMUM = 1.007626  # known optimum for n=3, for the normalized view
TOL = Fraction(1, 10**9)
REWARD_PATH = Path("/logs/verifier/reward.json")


def find_artifact(name: str) -> Path | None:
    hits = sorted(Path("/logs/artifacts").rglob(name))
    return hits[0] if hits else None


def grade() -> dict:
    solution = find_artifact("solution.json")
    if solution is None:
        return {"reward": 0.0, "reason": "no solution.json artifact"}
    try:
        circles = json.loads(solution.read_text())["circles"]
        parsed = [(Fraction(x), Fraction(y), Fraction(r)) for x, y, r in circles]
    except (KeyError, ValueError, TypeError) as e:
        return {"reward": 0.0, "reason": f"malformed solution: {e}"}
    if len(parsed) != 3:
        return {"reward": 0.0, "reason": "need exactly 3 circles"}

    one = Fraction(1)
    for x, y, r in parsed:
        if r <= 0:
            return {"reward": 0.0, "reason": "non-positive radius"}
        if x - r < -TOL or x + r > one + TOL or y - r < -TOL or y + r > one + TOL:
            return {"reward": 0.0, "reason": "circle outside unit square"}

    for i in range(3):
        for j in range(i + 1, 3):
            xi, yi, ri = parsed[i]
            xj, yj, rj = parsed[j]
            # Exact: dist^2 >= (ri + rj - tol)^2, no square roots involved.
            min_dist = ri + rj - TOL
            if min_dist > 0 and (xi - xj) ** 2 + (yi - yj) ** 2 < min_dist**2:
                return {"reward": 0.0, "reason": f"circles {i},{j} overlap"}

    total = float(sum(r for _, _, r in parsed))
    return {"reward": total, "normalized": total / OPTIMUM}


if __name__ == "__main__":
    result = grade()
    # Harbor's reward contract is numbers-only (VerifierResult.rewards is
    # dict[str, float | int]); the human-readable reason goes to the verifier
    # log dir instead.
    reason = result.pop("reason", "")
    REWARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REWARD_PATH.write_text(json.dumps(result))
    (REWARD_PATH.parent / "reason.txt").write_text(reason or "ok")
    print(json.dumps(result), reason)
