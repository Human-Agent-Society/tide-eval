"""Load real Tencent CL-bench data and build the ingest-then-probe arms.

    python examples/clbench_probes.py path/to/CL-bench.jsonl [n]

Download the JSONL from https://huggingface.co/datasets/tencent/CL-bench
(license: theirs — tide does not redistribute it). This script shows the
three probe arms tide derives from each record; judging them for real needs
an OpenAI-compatible key:

    from openai import AsyncOpenAI
    from tide.probe import openai_infer, openai_rubric_judge
    prober = ProbeExecutor(openai_infer(client), openai_rubric_judge(client, "gpt-5.1"))
    lab = Lab("runs/clbench", prober=prober)
    await lab.probe(p_in_context, {"model": ...}, tags={"arm": "in_context"})
"""

import sys

from tide.loaders import load_rubric_probes, reveal_phases, strip_context


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path, limit = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3

    probes = load_rubric_probes(path, limit=limit)
    print(f"loaded {len(probes)} probes from {path}\n")

    for probe in probes:
        in_context = probe  # capability upper bound
        from_state = strip_context(probe)  # after the learner ingested it
        phases = reveal_phases(probe, 3)  # AgentStream-style stream

        context_chars = sum(len(m["content"]) for m in in_context.messages)
        stripped_chars = sum(len(m["content"]) for m in from_state.messages)
        print(
            f"{probe.id}: {len(probe.rubrics)} rubrics · "
            f"in_context {context_chars} chars → from_state {stripped_chars} chars · "
            f"{len(phases)} reveal phases"
        )


if __name__ == "__main__":
    main()
