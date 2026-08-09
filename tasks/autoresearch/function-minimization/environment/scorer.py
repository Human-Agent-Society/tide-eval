"""Public scorer — the agent-facing fitness function (untrusted by design).

Levi function N.13: many local minima, global minimum 0 at (1, 1).
Reward = 1 / (1 + f(x, y)); the global optimum scores 1.0.
"""

import json
import math
import sys
from pathlib import Path


def f(x: float, y: float) -> float:
    return (
        math.sin(3 * math.pi * x) ** 2
        + (x - 1) ** 2 * (1 + math.sin(3 * math.pi * y) ** 2)
        + (y - 1) ** 2 * (1 + math.sin(2 * math.pi * y) ** 2)
    )


def score(path: str) -> float:
    point = json.loads(Path(path).read_text())
    return 1.0 / (1.0 + f(float(point["x"]), float(point["y"])))


if __name__ == "__main__":
    print(score(sys.argv[1] if len(sys.argv) > 1 else "/app/best/solution.json"))
