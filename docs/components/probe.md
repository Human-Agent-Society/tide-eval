# Probes

`tide/probe.py` — one prompt, one model response, one rubric judgment, no
container. Probes are what make dense per-phase capability tracking
affordable: an API call instead of a container build.

## The pieces

- **`Probe(id, messages, rubrics, data)`** — messages in OpenAI chat format;
  rubrics are natural-language criteria.
- **`ProbeExecutor(infer, judge)`** — both are async callables, deliberately
  pluggable:
  - `infer(messages, model) → str`
  - `judge(output, probe) → Rewards`
- Defaults for OpenAI-compatible stacks: `openai_infer(client)` and
  `openai_rubric_judge(client, judge_model)` (the CL-bench convention:
  `reward = 1.0` only if **all** rubrics pass; `fraction_passed` also
  reported). Requires `pip install "tide-eval[probe]"`.

## Judging rules

- The judge prompt asks for `<n>. PASS/FAIL` lines; `_parse_verdicts` is
  **conservative**: missing, malformed, or out-of-range lines count FAIL.
  An unparseable judgment never awards credit.
- Probes run **frozen**: whatever state the model was given is a materialized
  snapshot; probe trajectories never flow back into learner state. That rule
  lives in your stream script — keep it.

## How to modify

- **Different aggregation** (partial credit, weighted rubrics): write your
  own `judge` — it's one async function; don't extend the default.
- **Different judge model/provider**: construct `openai_rubric_judge` with
  any OpenAI-compatible client, or replace it entirely.
- **Ingest a rubric corpus** (e.g. Tencent CL-bench JSONL): each record maps
  to `Probe(id=idx, messages=record["messages"], rubrics=tuple(criteria))` —
  a ten-line loop, see the catalog entry in the README.
- **Caching / batching**: wrap `infer` — the executor doesn't care what's
  behind the callable.
