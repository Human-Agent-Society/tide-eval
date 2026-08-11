"""Console entry point for the Codex Goal harness package."""

from __future__ import annotations

import argparse
from pathlib import Path

from tide_codex_goal.app_server import run_goal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("objective", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--token-budget", type=int)
    args = parser.parse_args()
    run_goal(args.objective.read_text(), args.model, args.token_budget)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
