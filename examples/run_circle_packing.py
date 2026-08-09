"""Run the autoresearch exemplar for real (requires Docker + `pip install tide-eval[harbor]`).

Two runs prove the pipeline:

1. The **oracle** agent executes the task's own solution/ — it should score
   exactly 0.75, proving env build, artifact flow, and the separate verifier
   all work.
2. A real agent (claude-code here; any Harbor agent name works) tries to beat
   it within the budget.

    python examples/run_circle_packing.py            # oracle only
    python examples/run_circle_packing.py --agent claude-code --model anthropic/claude-opus-5
"""

import argparse
import asyncio
import sys
from pathlib import Path

from tide import Lab

TASK = str(Path(__file__).parent.parent / "tasks" / "circle-packing-mini")


async def main(agent: str, model: str | None, check: bool = False):
    lab = Lab("runs/circle-packing")

    oracle = await lab.run(TASK, {"name": "oracle"}, tags={"arm": "oracle"})
    print("oracle:", oracle.rewards)  # expect {"reward": 0.75, ...}
    if check:
        # E2E gate: the oracle must score exactly its known value, proving env
        # build, artifact flow, and the separate verifier end to end.
        if oracle.rewards.get("reward") != 0.75:
            print(f"E2E CHECK FAILED: expected reward 0.75, got {oracle.rewards}")
            sys.exit(1)
        print("E2E check passed: oracle scored 0.75 through the full pipeline")

    if agent != "oracle":
        agent_cfg = {"name": agent, **({"model_name": model} if model else {})}
        row = await lab.run(TASK, agent_cfg, tags={"arm": "agent"})
        print(f"{agent}:", row.rewards)

        trace = lab.df("trace")
        if not trace.empty:
            from tide import metrics

            print("\nanytime curve (untrusted, from the agent's score log):")
            print(metrics.anytime(trace)[["t", "score", "best_so_far"]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="oracle")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero unless the oracle scores exactly 0.75",
    )
    args = parser.parse_args()
    asyncio.run(main(args.agent, args.model, args.check))
