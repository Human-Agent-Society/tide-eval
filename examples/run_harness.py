"""Run one issue-4 harness on Tide's circle-packing task.

Examples:
    OPENAI_API_KEY=... python examples/run_harness.py openevolve --model gpt-5-mini
    OPENAI_API_KEY=... python examples/run_harness.py codex-goal --model gpt-5.6-terra
    OPENAI_API_KEY=... python examples/run_harness.py coral --model gpt-5.6-terra
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from tide import Lab

TASK = str(Path(__file__).parent.parent / "tasks" / "autoresearch" / "circle-packing")
AGENTS = {
    "openevolve": "examples.harnesses.openevolve.agent:OpenEvolveHarness",
    "codex-goal": "examples.harnesses.codex.agent:CodexGoalHarness",
    "coral": "examples.harnesses.coral.agent:CoralHarness",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("harness", choices=AGENTS)
    parser.add_argument("--model", required=True)
    parser.add_argument("--lab", default="runs/harnesses")
    parser.add_argument("--agents", type=int, default=2, help="CORAL worker count")
    parser.add_argument(
        "--iterations", type=int, default=100, help="OpenEvolve iterations"
    )
    parser.add_argument("--token-budget", type=int, help="Codex /goal token budget")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    kwargs = {
        "openevolve": {"iterations": args.iterations},
        "codex-goal": {"token_budget": args.token_budget},
        "coral": {"agents": args.agents},
    }[args.harness]
    lab = Lab(args.lab)
    row = await lab.run(
        TASK,
        agent={
            "import_path": AGENTS[args.harness],
            "model_name": args.model,
            # Harbor resolves the placeholder at runtime, so the key itself is
            # not serialized into the trial configuration.
            "env": {"OPENAI_API_KEY": "${OPENAI_API_KEY}"},
            "extra_allowed_hosts": ["api.openai.com"],
            "kwargs": kwargs,
        },
        tags={"harness": args.harness, "model": args.model},
    )
    print(row.rewards)
    print(
        {
            key: row.tags[key]
            for key in (
                "n_input_tokens",
                "n_cache_tokens",
                "n_output_tokens",
                "cost_usd",
            )
            if key in row.tags
        }
    )
    print(row.uri)


if __name__ == "__main__":
    asyncio.run(main())
