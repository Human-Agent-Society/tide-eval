"""Quickstart: the whole tide API in 30 seconds, no Docker required.

Runs episodes through the FakeExecutor so you can see the shape of the thing
— idempotency, tags, the DataFrame — before touching real containers.

    python examples/quickstart.py
"""

import asyncio

from tide import FakeExecutor, Lab
from tide.types import TracePoint


async def main():
    lab = Lab(
        "runs/quickstart",
        executor=FakeExecutor(  # swap for the default HarborExecutor in real runs
            score=lambda spec: {
                "reward": 0.6 if spec.agent["name"] == "smart" else 0.3
            },
            trace=lambda spec: [
                TracePoint(t=10, score=0.2),
                TracePoint(t=50, score=0.55),
            ],
        ),
    )

    # Episodes: one call = one trusted measurement. Tags are your dimensions.
    for agent in ("smart", "basic"):
        for attempt in range(3):
            await lab.run(
                "demo/circle-packing",
                {"name": agent},
                tags={"agent": agent, "attempt": attempt},
            )

    # Idempotency: this exact call already ran, so nothing executes.
    await lab.run(
        "demo/circle-packing", {"name": "smart"}, tags={"agent": "smart", "attempt": 0}
    )

    episodes = lab.df("episode")
    print(episodes[["task", "agent", "attempt", "reward"]])
    print("\nmean reward by agent:")
    print(episodes.groupby("agent")["reward"].mean())

    # Every episode also carried an (untrusted) score trajectory:
    from tide import metrics

    trace = lab.df("trace")
    curve = metrics.anytime(trace, by=["agent"])
    print("\nanytime AUC (agent=smart):", metrics.auc(curve[curve.agent == "smart"]))


if __name__ == "__main__":
    asyncio.run(main())
