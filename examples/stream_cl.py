"""A continual-learning stream, end to end, runnable offline.

Runs the ingest-then-probe protocol over the in-repo `ocean-facts` stream
benchmark (tasks/streams/ocean-facts):

  phase i: the learner INGESTS document i into its state folder
           → probe every question seen so far, WITHOUT the document in the
             prompt (knowledge must come from state)
           → also probe with a FRESH (empty) state as the control arm

The learner here is deliberately dumb (it just saves the documents) and the
"model" is a fake that answers from whatever state it was given — the point
is the *harness*: state versioning, frozen probes, and the gain/forgetting
metrics falling out of the store as queries. Swap in a real model + judge
per the markers below.

    python examples/stream_cl.py
"""

import asyncio
import json
import shutil
from pathlib import Path

from tide import FakeExecutor, Lab, Probe, ProbeExecutor, StateDir, metrics

BENCH = Path(__file__).parent.parent / "tasks" / "streams" / "ocean-facts"


def load_bench():
    facts = {
        r["name"]: r["text"]
        for r in map(json.loads, (BENCH / "facts.jsonl").read_text().splitlines())
    }
    probes = []
    for r in map(json.loads, (BENCH / "probes.jsonl").read_text().splitlines()):
        probes.append(
            Probe(
                id=f"probe/{r['metadata']['fact']}",
                messages=r["messages"],
                rubrics=tuple(r["rubrics"]),
                data=r["metadata"],
            )
        )
    order = json.loads((BENCH / "manifest.json").read_text())["order"]
    return facts, probes, order


def fake_model(state_dir: Path | None):
    """'Inference' that can only answer from its state folder — a stand-in
    for a real memory-augmented agent. Swap for openai_infer in real runs."""

    async def infer(messages, model):
        knowledge = ""
        if state_dir and state_dir.exists():
            knowledge = " ".join(p.read_text() for p in sorted(state_dir.glob("*.txt")))
        question = messages[-1]["content"]
        for probe_id, keyword in infer.answers.items():
            if question == probe_id and keyword in knowledge:
                return keyword  # it "remembers"
        return "I don't know."

    infer.answers = {}
    return infer


async def judge(output, probe):
    # Stand-in rubric judge: swap for openai_rubric_judge in real runs.
    keyword = probe.data["answer_keyword"]
    return {"reward": 1.0 if keyword in output else 0.0}


async def main():
    shutil.rmtree("runs/stream-cl", ignore_errors=True)
    facts, probes, order = load_bench()
    by_name = {p.data["fact"]: p for p in probes}
    state = StateDir("runs/stream-cl/state")

    async def probe_arm(arm: str, state_path, phase: int):
        infer = fake_model(state_path)
        infer.answers = {
            by_name[n].messages[-1]["content"]: by_name[n].data["answer_keyword"]
            for n in order
        }
        lab = Lab(
            "runs/stream-cl",
            executor=FakeExecutor(),
            prober=ProbeExecutor(infer, judge),
        )
        for name in order[: phase + 1]:  # probe everything seen so far
            await lab.probe(by_name[name], tags={"phase": phase, "arm": arm})

    for i, name in enumerate(order):
        # LEARN: ingest into the state folder; snapshot = the version.
        (state.path / f"{name}.txt").write_text(facts[name])
        ref = state.snapshot(f"phase {i}: ingested {name}")
        print(f"phase {i}: ingested {name!r} -> {ref[:8]}")

        # PROBE (frozen): materialized copy, so probing can't mutate state.
        frozen = state.materialize(ref)
        await probe_arm("stateful", frozen, i)
        await probe_arm("fresh", None, i)  # control arm

    lab = Lab("runs/stream-cl", executor=FakeExecutor())
    results = lab.df("probe")

    print("\naccuracy matrix (phase x task, stateful arm):")
    m = metrics.matrix(results[results.arm == "stateful"])
    print(m)
    print("\nforgetting per task:", metrics.forgetting(m).to_dict())
    print("\ngain (stateful - fresh) by phase:")
    print(metrics.gain(results, by=["phase"]))


if __name__ == "__main__":
    asyncio.run(main())
