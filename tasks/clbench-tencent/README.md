# Tencent CL-bench / CL-bench Life

Rubric-judged context-learning corpora from
[Tencent-Hunyuan/CL-bench](https://github.com/Tencent-Hunyuan/CL-bench):
1,899 expert-annotated professional tasks plus 405 real-life ones, each a
(system + context + question) prompt with pass/fail rubrics. Licensed by
Tencent — fetched locally, never redistributed here.

```bash
python tasks/clbench-tencent/fetch.py          # CL-bench.jsonl (~90 MB)
python tasks/clbench-tencent/fetch.py life     # CL-bench-Life.jsonl
```

These are probes, not container tasks. Three arms per record:

```python
from tide.loaders import load_rubric_probes, strip_context, reveal_phases

probes = load_rubric_probes("tasks/clbench-tencent/CL-bench.jsonl", limit=50)
p = probes[0]
in_context = p  # original: context in the prompt (upper bound)
from_state = strip_context(p)  # question only — knowledge must come from learner state
stream = reveal_phases(p, 3)  # AgentStream-style progressive reveal

# judge with tide.probe.openai_rubric_judge (all-rubrics-pass, their protocol);
# metrics.internalization reads the in_context/from_state pair.
```

See `examples/stream_cl.py` for the full ingest-then-probe protocol these
arms plug into.
