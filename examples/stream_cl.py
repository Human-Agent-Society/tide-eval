"""A continual-learning stream, end to end, runnable offline.

The protocol is the ingest-then-probe pattern (how you turn context-learning
corpora like CL-bench into a real CL measurement):

  phase i: the learner INGESTS a document into its state folder
           → probe every task seen so far, WITHOUT the document in the prompt
           → also probe with a FRESH (empty) state as the control arm

The learner here is deliberately dumb (it just saves the documents) and the
"model" is a fake that answers from whatever state it was given — the point
is the *harness*: state versioning, frozen probes, and the gain/forgetting
metrics falling out of the store as queries.

    python examples/stream_cl.py
"""

import asyncio
import shutil
from pathlib import Path

from tide import FakeExecutor, Lab, Probe, ProbeExecutor, StateDir, metrics

# The stream: each phase teaches one fact; its probe asks for it back.
STREAM = [
    ("tides",   "Spring tides occur when the sun and moon align.",
                "What causes spring tides?",            "mentions sun and moon aligning"),
    ("reefs",   "Coral bleaching is driven by heat stress.",
                "What drives coral bleaching?",         "mentions heat stress"),
    ("currents", "The gulf stream moves warm water north.",
                "What does the gulf stream transport?", "mentions warm water"),
]


def fake_model(state_dir: Path | None):
    """'Inference' that can only answer from its state folder — a stand-in
    for a real memory-augmented agent. Swap for openai_infer in real runs."""

    async def infer(messages, model):
        question = messages[-1]["content"]
        knowledge = ""
        if state_dir and state_dir.exists():
            knowledge = " ".join(
                p.read_text() for p in sorted(state_dir.glob("*.txt"))
            )
        for _, fact, q, _ in STREAM:
            if q == question and fact in knowledge:
                return fact  # it "remembers"
        return "I don't know."

    return infer


async def judge(output, probe):
    # Stand-in rubric judge: swap for openai_rubric_judge in real runs.
    keyword = probe.data["keyword"]
    return {"reward": 1.0 if keyword in output else 0.0}


async def main():
    shutil.rmtree("runs/stream-cl", ignore_errors=True)
    state = StateDir("runs/stream-cl/state")

    async def probe_arm(lab_arm: str, state_path, phase: int, upto: int):
        lab = Lab(
            "runs/stream-cl",
            executor=FakeExecutor(),
            prober=ProbeExecutor(fake_model(state_path), judge),
        )
        for j in range(upto + 1):
            name, fact, question, rubric = STREAM[j]
            await lab.probe(
                Probe(id=f"probe/{name}",
                      messages=[{"role": "user", "content": question}],
                      rubrics=(rubric,),
                      data={"keyword": fact}),
                tags={"phase": phase, "arm": lab_arm},
            )

    for i, (name, fact, _, _) in enumerate(STREAM):
        # LEARN: ingest into the state folder; snapshot = the version.
        (state.path / f"{name}.txt").write_text(fact)
        ref = state.snapshot(f"phase {i}: ingested {name}")
        print(f"phase {i}: ingested {name!r} -> {ref[:8]}")

        # PROBE (frozen): materialized copy, so probing can't mutate state.
        frozen = state.materialize(ref)
        await probe_arm("stateful", frozen, i, upto=i)
        await probe_arm("fresh", None, i, upto=i)      # control arm

    lab = Lab("runs/stream-cl", executor=FakeExecutor())
    probes = lab.df("probe")

    print("\naccuracy matrix (phase x task, stateful arm):")
    m = metrics.matrix(probes[probes.arm == "stateful"])
    print(m)
    print("\nforgetting per task:", metrics.forgetting(m).to_dict())
    print("\ngain (stateful - fresh) by phase:")
    print(metrics.gain(probes, by=["phase"]))


if __name__ == "__main__":
    asyncio.run(main())
