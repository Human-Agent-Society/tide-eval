"""Quickstart: the Lab API in 30 seconds, offline.

No Docker and no real agents run here: the FakeExecutor **simulates**
episode results so you can see the shape of the thing — idempotency, tags,
trace rows, the DataFrame. The agent names below ("strong", "weak") are
just labels our fake scorer reacts to; they are not defined anywhere else.

Real runs replace the FakeExecutor with the default HarborExecutor and a
real agent:

    tide run autoresearch --agent claude-code --model ...   # supported harness
    python examples/minimal_harness.py                      # your own harness

    python examples/quickstart.py
"""

import asyncio

from tide import FakeExecutor, Lab, metrics
from tide.types import TracePoint

# Simulate: "strong" scores 0.6, anyone else 0.3; every episode also
# claims a two-point score log.
fake = FakeExecutor(
    score=lambda spec: {"reward": 0.6 if spec.agent["name"] == "strong" else 0.3},
    trace=lambda spec: [TracePoint(t=10, score=0.2), TracePoint(t=50, score=0.55)],
)


async def main():
    lab = Lab("runs/quickstart", executor=fake)

    # Episodes: one call = one trusted measurement. Tags are your dimensions.
    for agent in ("strong", "weak"):
        for attempt in range(3):
            await lab.run(
                "demo/circle-packing",
                {"name": agent},
                tags={"agent": agent, "attempt": attempt},
            )

    # Idempotency: this exact call already ran, so nothing executes.
    await lab.run(
        "demo/circle-packing",
        {"name": "strong"},
        tags={"agent": "strong", "attempt": 0},
    )

    episodes = lab.df("episode")
    print(episodes[["task", "agent", "attempt", "reward"]])
    print("\nmean reward by agent:")
    print(episodes.groupby("agent")["reward"].mean())

    # Every episode also carried an (untrusted) score log:
    trace = lab.df("trace")
    curve = metrics.anytime(trace, by=["agent"])
    print("\nanytime AUC (agent=strong):", metrics.auc(curve[curve.agent == "strong"]))


if __name__ == "__main__":
    asyncio.run(main())
