"""Public scorer — the agent-facing fitness function.

Deliberately unisolated: the agent may call, read, or even tamper with this
file, and none of that matters because the trusted grade is recomputed from
scratch in a separate verifier container (see tests/grade.py, which shares
this logic at stricter tolerance).
"""

import json
import math
import sys

TOL = 1e-9


def score(path: str) -> float:
    with open(path) as f:
        circles = json.load(f)["circles"]
    if len(circles) != 3:
        return 0.0
    for x, y, r in circles:
        if r <= 0 or x - r < -TOL or x + r > 1 + TOL or y - r < -TOL or y + r > 1 + TOL:
            return 0.0
    for i in range(len(circles)):
        for j in range(i + 1, len(circles)):
            xi, yi, ri = circles[i]
            xj, yj, rj = circles[j]
            if math.dist((xi, yi), (xj, yj)) < ri + rj - TOL:
                return 0.0
    return sum(r for _, _, r in circles)


if __name__ == "__main__":
    print(score(sys.argv[1] if len(sys.argv) > 1 else "/app/best/solution.json"))
