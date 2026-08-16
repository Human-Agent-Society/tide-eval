"""Fetch terminal-bench 2.0 — stock Harbor pass/fail tasks, pinned.

    python tasks/terminal-bench/fetch.py                  # all 89 tasks
    python tasks/terminal-bench/fetch.py chess-best-move  # just the named ones
    python tasks/terminal-bench/fetch.py --limit 10       # first 10 — a starter stream

Only terminal-bench **2.0** is supported: the pin below is the exact
commit the Harbor registry publishes as v2.0. terminal-bench 1.x predates
the Harbor task format and is deliberately not included. Tasks land next
to this script unchanged — they are already stock Harbor tasks, nothing is
converted — and stay git-ignored, because the pin makes any fetch
reproducible. Then:

    tide stream week1 terminal-bench --agent claude-code --model anthropic/claude-opus-5
"""

import argparse
from pathlib import Path

from tide.fetch import fetch_pinned_tasks

# The exact commit the Harbor registry pins as terminal-bench v2.0.
# Upstream: harbor-framework/terminal-bench-2 (Apache-2.0).
GIT_URL = "https://github.com/laude-institute/terminal-bench-2.git"
COMMIT = "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="fetch terminal-bench 2.0 tasks (pinned)"
    )
    parser.add_argument("tasks", nargs="*", help="task names (default: all 89)")
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N", help="only the first N tasks"
    )
    args = parser.parse_args()

    dest = Path(__file__).parent
    copied = fetch_pinned_tasks(
        GIT_URL, COMMIT, dest, only=args.tasks or None, limit=args.limit
    )
    print(f"fetched {len(copied)} terminal-bench 2.0 task(s) -> {dest}")
    print("stream them: tide stream week1 terminal-bench --agent <a> --model <m>")


if __name__ == "__main__":
    main()
