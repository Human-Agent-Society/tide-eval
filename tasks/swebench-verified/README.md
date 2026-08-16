# SWE-bench Verified — the hard AgentStream pick

**What**: [SWE-bench Verified](https://github.com/SWE-bench/SWE-bench) —
500 real-world software-engineering tasks (fix a reported issue in a real
repository), in the stock Harbor task format published by
[harbor-datasets](https://github.com/laude-institute/harbor-datasets).
Pass/fail: a resolved issue is reward 1.0.

**Why it's here**: the [AgentStream](https://arxiv.org/abs/2608.00155)
paper builds its continual-learning task streams from six benchmarks —
AppWorld, BFCL, BrowseComp-Plus, HLE, SWE-bench Verified, and Tau2.
Of those, SWE-bench Verified is the hardest one available in the Harbor
task format today, so it is the one tide supports. The others (including
HLE and BrowseComp-Plus, the two the paper measures as hardest) have no
published Harbor version yet.

**License**: the upstream dataset repository carries no license, so the
tasks are never committed here — [`fetch.py`](fetch.py) fetches them onto
your machine from the exact commit the Harbor registry pins as v1.0, and
the blob filter keeps a subset fetch small:

```bash
tide fetch swebench-verified --limit 50   # a stream-sized subset · or task names · or all 500
tide stream week1 swebench-verified --agent claude-code --model anthropic/claude-opus-5
```

Streams run in name order with the agent's memory (`$TIDE_STATE_DIR`)
carried from task to task; list task folders yourself for a custom order
or repeats. The isolated control arm for `metrics.transfer` is a plain
`tide run swebench-verified/<task> --agent <a>` over the same tasks.
