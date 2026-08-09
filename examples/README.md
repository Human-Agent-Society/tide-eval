# Examples

One entry point per supported benchmark family. Offline ones run with zero
setup; the rest state their requirements up front.

| Script | What it shows | Needs |
|---|---|---|
| [`quickstart.py`](quickstart.py) | the whole Lab API in 30 seconds | nothing |
| [`stream_cl.py`](stream_cl.py) | a complete continual-learning stream: ingest → snapshot → frozen probes → gain & forgetting | nothing |
| [`run_circle_packing.py`](run_circle_packing.py) | the autoresearch exemplar end-to-end; `--check` is the CI gate | Docker + `[harbor]` |
| [`run_frontiercs.py`](run_frontiercs.py) | a FrontierCS 2.0 task (pinned erdos export) under any Harbor agent | Docker + `[harbor]` |
| [`convert_edgebench.py`](convert_edgebench.py) | fetch EdgeBench specs from HF and convert to Harbor task dirs | network + `[converters]` |
| [`clbench_probes.py`](clbench_probes.py) | real Tencent CL-bench data → in-context / from-state / reveal-phase arms | the JSONL from HF |
| [`reef_weightplane.py`](reef_weightplane.py) | reef as the weight plane: version-pinned eval + report loop | a running `reef serve` |
| [`tasks/circle-packing-mini/`](tasks/circle-packing-mini) | the reference autoresearch task: dual scorer, separate verifier, budget semantics | — |
