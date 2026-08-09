# ocean-facts

A tiny, fully offline continual-learning stream: 8 documents (facts), each
paired with a probe question and a rubric. The protocol is ingest-then-probe:

- **learn** phase i: the learner ingests document i into its state folder;
- **probe**: every question seen so far is asked **without** the document in
  the prompt — knowledge must come from the learner's state;
- a **fresh** control arm answers with empty state; stateful − fresh is the
  gain metric, and re-probing old facts over time draws the forgetting curve.

Run the whole protocol offline: `python examples/stream_cl.py`
(loads this folder; swap the fake model/judge for real ones per its docstring).

Load the probes yourself:

```python
from tide.loaders import load_rubric_probes

probes = load_rubric_probes("tasks/streams/ocean-facts/probes.jsonl")
```

This is the smallest possible instance of the pattern; `hidden-rules/` next
door is the harder one (a latent structure worth accumulating evidence for).
