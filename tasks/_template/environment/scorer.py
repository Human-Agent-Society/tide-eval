"""Public scorer — the agent-facing fitness function (untrusted by design).

The agent may call, read, or even tamper with this file; none of that matters
because the trusted grade is recomputed from scratch in a separate container.
"""

import json
import sys
from pathlib import Path


def score(path: str) -> float:
    solution = json.loads(Path(path).read_text())  # noqa: F841
    raise NotImplementedError("TODO(task): compute the score")


if __name__ == "__main__":
    print(score(sys.argv[1] if len(sys.argv) > 1 else "/app/best/solution.json"))
