"""Console entry point for the Codex Goal harness package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tide_codex_goal.app_server import run_goal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("objective", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--token-budget", type=int)
    parser.add_argument("--usage-file", type=Path)
    args = parser.parse_args()
    usage = run_goal(
        args.objective.read_text(),
        args.model,
        args.token_budget,
        args.usage_file,
    )
    if usage:
        value = json.dumps(usage, separators=(",", ":"))
        print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
