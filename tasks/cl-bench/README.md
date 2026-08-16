# CL-Bench — continual learning as task streams

**What**: [Continual Learning Bench](https://www.continual-learning-bench.com)
([paper](https://arxiv.org/pdf/2606.05661), Apache-2.0) — expert-validated
tasks where an agent works through **sequential instances of one
environment** and should improve by remembering what it saw: the exact
setting tide streams exist for. Their *system* (agent + memory strategy)
is tide's agent + carried `$TIDE_STATE_DIR`; their *gain metric*
(stateful minus stateless reward) is exactly `metrics.transfer` — the
stream against a plain isolated `tide run` sweep over the same tasks.

**Converted today: the blind-spectrum-monitoring domain** — 90 scans of a
radio band whose persistent transmitter layout (including dormant
channels, with drift across three lifecycle stages) must be inferred over
time. One scan = one Harbor task named `bsm-sNN`, so name order replays
the published lifecycle. Upstream reveals no ground truth between scans —
the learnable signal is the scan history itself, which is precisely what
the stream's carried memory holds. Scoring is the upstream interval-IoU
metric, ported verbatim ([`score_bsm.py`](score_bsm.py)): deterministic,
offline, no LLM judge. The reference solution (derived from ground truth)
scores exactly 1.0, so the oracle proves the pipeline.

CL-Bench's other five domains (codebase adaptation, cohort studies,
database exploration, exploitable poker, sales prediction) are
interactive environments that need more than a prompt-and-score
conversion; they are tracked in the
[roadmap](https://github.com/Human-Agent-Society/tide-eval/issues/19).

**Get the tasks** (generated from the pinned upstream commit; the corpus
is integrity-checked against the sha256 its own metadata declares):

```bash
tide fetch cl-bench                # all 90 scans · or --limit 10
tide stream my-stream cl-bench --agent claude-code --model anthropic/claude-opus-5
```

The isolated control arm for `metrics.transfer` — CL-Bench's gain — is a
plain `tide run cl-bench/<task> --agent <a>` over the same tasks.
