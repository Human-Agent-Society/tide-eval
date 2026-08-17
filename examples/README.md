# Examples

Three examples, one per thing worth learning first. The first two run
with zero setup.

| Script | What it shows | Needs |
|---|---|---|
| [`quickstart.py`](quickstart.py) | the Lab API: episodes, budgets, the results table (agents are simulated) | nothing |
| [`stream_quickstart.py`](stream_quickstart.py) | a continual-learning stream: carried state, the learning curve, resume | nothing |
| [`minimal_harness.py`](minimal_harness.py) | the smallest real agent harness: a ~25-line `BaseAgent` plus a submit-loop search through the full pipeline | Docker + `[harbor]` |

For the real container pipeline in one line, run the oracle on any task:
`tide run autoresearch/first-party/circle-packing --agent oracle` must
score exactly 0.75.

## Reference harness adapters

[`harnesses/`](harnesses) holds comparable OpenEvolve, Codex, and CORAL
adapters, all submitting to the same judge, with `run_harness.py` as the
entry point. These are baselines for comparison, not a starting point;
begin with `minimal_harness.py`.
