# CL-Bench — continual learning as task streams

**What**: [Continual Learning Bench](https://www.continual-learning-bench.com)
([paper](https://arxiv.org/pdf/2606.05661), Apache-2.0) — expert-validated
tasks where an agent works through **sequential instances of one
environment** and should improve by remembering what it saw: the exact
setting tide streams exist for. Their *system* (agent + memory strategy)
is tide's agent + carried `$TIDE_STATE_DIR`; their *gain metric*
(stateful minus stateless reward) is exactly `metrics.transfer` — the
stream against a plain isolated `tide run` sweep over the same tasks.

**All six domains are converted** — 301 tasks, the benchmark's full
instance count, every scorer deterministic and offline (no LLM judge
anywhere). One instance = one Harbor task; name order replays each
domain's upstream lifecycle:

| Domain | Tasks | What it is | Reward |
|---|---|---|---|
| `bsm-sNN` | 90 | infer a radio band's persistent transmitter layout across scans, through drift | long-run availability IoU (0–1) |
| `sales-iNN` | 12 | yearly 5-year demand forecasts from a shifting one-store data room | WAPE-skill (1 = perfect, negative possible) |
| `cohort-iNN` | 20 | rolling survival meta-analysis across biased studies; 36 cohorts no single study observes | information gain in bits over the study-wide baseline |
| `code-iNN` | 19 | sequential real-PR bugfixes in tablib, then tenacity | hidden tests pass = 1.0 |
| `dbx-qNN` | 40 | questions over an undocumented SQLite db with a 15-query budget; schema migrates at q21 | 1 − queries/15 if correct, else 0 |
| `poker-hNNN` | 120 | deterministic heads-up hold'em vs three exploitable scripted opponents | profit in big blinds |

**How the conversions work** (`convert_<domain>.py` beside this file):

- **bsm / sales / cohort** generate self-contained predict-and-score
  tasks; the data rooms and scorers are the upstream code, vendored
  verbatim where practical (`vendor_sales.py`, `score_*.py` headers say
  exactly what was ported).
- **codebase** builds on the upstream-published Docker images (repo with
  full git history), prepares the workspace at image build exactly as
  upstream does, and the verifier replays the upstream evaluation:
  sanitize the agent's `git diff` of test-owned paths, reset, re-apply
  the official test patch, run the exact FAIL_TO_PASS + PASS_TO_PASS
  pytest node ids.
- **dbx / poker** keep their hidden state (the database, the deck and
  both hands) in a **judge sidecar** the agent reaches only over HTTP —
  the query meter and the deal are enforced where the agent cannot touch
  them, the same trust model as tide's autoresearch judge. Decks are
  dealt with the upstream seed-plus-burn recipe, verified card-for-card
  against the upstream harness.

**Oracle-checked**: every task ships a reference solution with a known
exact score — the truth-derived report (bsm 1.0, sales 1.0, cohort = the
per-instance ceiling recorded as `oracle_score`), the gold PR patch
(codebase 1.0), the direct correct answer (dbx 1.0), or a simulated
check/call line (poker, per-hand `oracle_reward`).

**Honest deviations from upstream**, per domain: sales/cohort/codebase
replace the upstream step- or action-metered interaction with free shell
work under a time budget (codebase's step-count reward shaping becomes
pass/fail; cohort's six-tool API becomes direct SQLite access); the
persistent workspace is `$TIDE_STATE_DIR` rather than a reused `/app`;
and where upstream delivered feedback conversationally, the converted
instructions carry the same information (dbx: the previous question's
correct answer) or it is self-served from the refreshed data (sales).
The dbx query budget and the poker deal are *not* deviations — the
sidecar enforces them exactly.

**All 301 tasks are committed here**, so they run out of the box.
[`fetch.py`](fetch.py) regenerates them from the pinned sources (upstream
commit, HuggingFace revisions, sha256-verified corpora; regenerating the
poker domain needs `pip install texasholdem==0.11.0` for the oracle
simulation):

```bash
tide stream my-stream tasks/cl-bench/poker-* --agent claude-code --model anthropic/claude-opus-5
tide fetch cl-bench bsm sales       # only to regenerate from the pins
```

Stream one domain with a shell glob as above (each domain is its own
lifecycle), or the whole folder in name order. The isolated control arm
for `metrics.transfer` — CL-Bench's gain — is a plain
`tide run cl-bench/<task> --agent <a>` over the same tasks.

Heads-up on scale: dbx task images download the published databases
(~0.4 GB each, cached across tasks by Docker layer), and codebase tasks
pull the upstream repo images on first build.
