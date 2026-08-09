"""Public scorer (untrusted by design). Reward = identity-tour length / yours."""

import json
import math
import sys
from pathlib import Path

CITIES = json.loads(Path("/app/cities.json").read_text())["cities"]


def tour_length(order):
    n = len(order)
    return sum(
        math.dist(CITIES[order[i]], CITIES[order[(i + 1) % n]]) for i in range(n)
    )


def score(path: str) -> float:
    tour = json.loads(Path(path).read_text())["tour"]
    baseline = tour_length(list(range(len(CITIES))))
    return baseline / tour_length(tour)


if __name__ == "__main__":
    print(score(sys.argv[1] if len(sys.argv) > 1 else "/app/best/solution.json"))
