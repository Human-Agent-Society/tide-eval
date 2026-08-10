"""Public scorer — the agent-facing fitness function (untrusted by design).

The agent may call, read, or even tamper with this file; none of that matters
because the trusted grade is recomputed from scratch in a separate container.

TODO(task): replace score() with your scoring rule; keep the CLI shape.
"""

import json
import sys
from pathlib import Path

TOL = 1e-9  # the public side may be float-tolerant; the private grader is exact


def score(path: str) -> float:
    solution = json.loads(Path(path).read_text())
    x = float(solution["x"])
    if x < -TOL or x > 1 + TOL:
        return 0.0
    return x


if __name__ == "__main__":
    print(score(sys.argv[1] if len(sys.argv) > 1 else "/app/best/solution.json"))
