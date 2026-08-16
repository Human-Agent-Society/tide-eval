"""Fetch SWE-bench Verified as stock Harbor tasks, pinned.

    python tasks/swebench-verified/fetch.py --limit 50        # a stream-sized subset
    python tasks/swebench-verified/fetch.py django__django-15098  # named tasks
    python tasks/swebench-verified/fetch.py                   # all 500

SWE-bench Verified is one of the six benchmarks the AgentStream paper
(arXiv:2608.00155) builds its task streams from, and of those six it is
the hardest one published in the Harbor task format so far. The pin below
is the exact commit the Harbor registry publishes as v1.0. The upstream
dataset repository carries no license, so these tasks are never committed
here — this script fetches them onto your machine, and the blob filter
keeps a `--limit` fetch small even though the full repository is huge.

    tide stream week1 swebench-verified --agent claude-code --model anthropic/claude-opus-5
"""

import argparse
from pathlib import Path

from tide.fetch import fetch_pinned_tasks

# The exact commit the Harbor registry pins as swebench-verified v1.0.
# Upstream: harbor-framework/harbor-datasets (no license — never vendored).
GIT_URL = "https://github.com/laude-institute/harbor-datasets.git"
COMMIT = "86723674f04e4209ac479d0fb75d9d9f44b4377e"
SUBDIR = "datasets/swebench-verified"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="fetch SWE-bench Verified tasks (pinned)"
    )
    parser.add_argument("tasks", nargs="*", help="task names (default: all 500)")
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N", help="only the first N tasks"
    )
    args = parser.parse_args()

    dest = Path(__file__).parent
    copied = fetch_pinned_tasks(
        GIT_URL, COMMIT, dest, subdir=SUBDIR, only=args.tasks or None, limit=args.limit
    )
    print(f"fetched {len(copied)} SWE-bench Verified task(s) -> {dest}")
    print("stream them: tide stream week1 swebench-verified --agent <a> --model <m>")


if __name__ == "__main__":
    main()
