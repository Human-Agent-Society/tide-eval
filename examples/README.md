# Examples

One entry point per supported benchmark family. Offline ones run with zero
setup; the rest state their requirements up front.

| Script | What it shows | Needs |
|---|---|---|
| [`quickstart.py`](quickstart.py) | the Lab API in 30 seconds — agents are *simulated* by the FakeExecutor | nothing |
| [`minimal_harness.py`](minimal_harness.py) | the smallest *real* agent harness: a ~25-line `BaseAgent` + a submit-loop random search (no LLM, no keys) through the full pipeline | Docker + `[harbor]` |
| [`run_circle_packing.py`](run_circle_packing.py) | the autoresearch exemplar end-to-end (oracle must score exactly 0.75) | Docker + `[harbor]` |
| [`../tasks/`](../tasks) | the benchmark catalog: one folder per benchmark, vendored or fetchable | see its README |
