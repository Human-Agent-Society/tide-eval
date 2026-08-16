# CL-bench — context learning as task streams

**What**: [CL-bench](https://www.clbench.com) ([paper](https://arxiv.org/abs/2602.03587),
Tencent Hunyuan & Fudan NLP) — 1,899 tasks over 500 expert-written
contexts (game rulebooks, legal codes, lab procedures, empirical data…).
Solving a task requires learning from the provided context rather than
pre-trained knowledge; frontier models average ~17% solved. 51.1% of the
tasks are **sequential** — later turns of the same context depend on
earlier ones — which is why it converts so naturally to streams.

**Conversion** ([`convert.py`](convert.py)): one record = one Harbor
task. The record's transcript (context, earlier turns with their
reference responses, the final task) becomes the instruction; the agent
writes its answer to `/app/answer.md`. Task folders are named
`<context8>-tNN`, so name order is context-blocked and turn-ordered —
streaming the folder replays each context's turns in sequence,
CL-bench's own protocol, with the agent's memory (`$TIDE_STATE_DIR`)
carried across turns.

**Grading** ([`judge.py`](judge.py)): the official rubric protocol,
ported verbatim from their `eval.py` so numbers stay comparable — one
LLM call checks all rubrics, all-or-nothing (reward 1 only if every
rubric passes), empty answer scores 0 without an API call. Deviation:
an unreachable judge is surfaced as a verifier error instead of a 0 —
infrastructure failure is not model failure. The judge needs a key on
the host at verify time; defaults are the paper's (gpt-5.1):

```bash
export OPENAI_API_KEY=...                 # or CLBENCH_JUDGE_API_KEY
# another provider: CLBENCH_JUDGE_BASE_URL + CLBENCH_JUDGE_MODEL
# (e.g. https://api.anthropic.com/v1 + an Anthropic key/model)
```

**License**: CL-bench's own terms — copying and use are permitted for
**evaluation/benchmarking only, never training**. Tasks are generated on
your machine from the pinned HuggingFace revision and are not committed
here:

```bash
tide fetch cl-bench --contexts 5    # first 5 contexts · or context-id prefixes · or all 500
tide stream week1 cl-bench --agent claude-code --model anthropic/claude-opus-5
```

The isolated control arm for `metrics.transfer` is a plain
`tide run cl-bench/<task> --agent <a>` over the same tasks.
