"""Public scorer (untrusted by design). Reward = first-fit bins / your bins."""

import json
import sys
from pathlib import Path

_DATA = json.loads(Path("/app/items.json").read_text())
ITEMS, CAPACITY = _DATA["items"], _DATA["capacity"]


def first_fit_bins() -> int:
    bins = []
    for size in ITEMS:
        for i, load in enumerate(bins):
            if load + size <= CAPACITY:
                bins[i] += size
                break
        else:
            bins.append(size)
    return len(bins)


def score(path: str) -> float:
    bins = json.loads(Path(path).read_text())["bins"]
    assert sorted(i for b in bins for i in b) == list(range(len(ITEMS)))
    assert all(sum(ITEMS[i] for i in b) <= CAPACITY for b in bins)
    return first_fit_bins() / len(bins)


if __name__ == "__main__":
    print(score(sys.argv[1] if len(sys.argv) > 1 else "/app/best/solution.json"))
