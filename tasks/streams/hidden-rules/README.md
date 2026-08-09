# hidden-rules

A continual-learning stream in the Continual-Learning-Bench style (episodes
sharing a **learnable latent structure**), fully offline and first-party.
The real thing lives at [pgasawa/continual-learning-bench](https://github.com/pgasawa/continual-learning-bench) (see
`tasks/continual-learning-bench/`); this is the smallest readable instance
of its protocol shape.

**The latent**: a hidden linear rule over 4 card features decides WIN/LOSS.
Each of 6 phases shows 8 observed rounds and asks for predictions on 4
unseen rounds (rubrics check exact `Round n: WIN/LOSS` lines).

**Why it measures continual learning**: 8 observations pin the rule poorly;
48 pin it well. A learner that accumulates observations across phases (in
its state folder) beats one that sees only the current phase, and the gap —
`metrics.gain`, stateful arm minus fresh arm — should **widen phase by
phase**. A flat gain curve means the learner isn't actually learning.

```python
from tide.loaders import load_rubric_probes

phases = load_rubric_probes("tasks/streams/hidden-rules/episodes.jsonl")
# arm 1 (fresh): probe each phase as-is — only the current 8 observations
# arm 2 (stateful): before probing phase i, ingest phases 0..i-1's
#   observations into the learner's state; probe with that state attached
# metrics.gain(df, by=["phase"]) → should increase with phase
```

`generate.py` (seeded) produced `episodes.jsonl` verbatim — regenerate to
verify, or change the seed/weights to mint fresh instances for held-out runs.
