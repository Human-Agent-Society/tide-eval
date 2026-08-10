"""Run the autoresearch exemplar for real (requires Docker + `pip install tide-eval[harbor]`).

Two runs prove the pipeline:

1. The **oracle** agent executes the task's own solution/ — it should score
   exactly 0.75, proving env build, artifact flow, and the separate verifier
   all work. (CI enforces this for every first-party task via
   scripts/e2e_oracle.py.)
2. A real agent (claude-code here; any Harbor agent name works) tries to beat
   it within the budget.

    python examples/run_circle_packing.py            # oracle only
    python examples/run_circle_packing.py --agent claude-code --model anthropic/claude-opus-5
"""

import argparse
import asyncio
from pathlib import Path

from tide import Lab, metrics

TASK = str(Path(__file__).parent.parent / "tasks" / "autoresearch" / "circle-packing")


async def main(agent: str, model: str | None):
    lab = Lab("runs/circle-packing")

    oracle = await lab.run(TASK, {"name": "oracle"}, tags={"arm": "oracle"})
    print("oracle:", oracle.rewards)  # expect {"reward": 0.75}

    if agent != "oracle":
        agent_cfg = {"name": agent, **({"model_name": model} if model else {})}
        row = await lab.run(TASK, agent_cfg, tags={"arm": "agent"})
        print(f"{agent}:", row.rewards)

        trace = lab.df("trace")
        if not trace.empty:
            print("\nanytime curve (untrusted, from the agent's score log):")
            print(metrics.anytime(trace)[["t", "score", "best_so_far"]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="oracle")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    asyncio.run(main(args.agent, args.model))
