# Authoring tasks & benchmarks

Tasks are **100% stock Harbor tasks**: every committed task is validated
against Harbor's `TaskConfig` schema by `tests/test_task_suite.py`. tide
adds conventions *around* the format, never fields inside it. Start from
[`tasks/_template`](../../tasks/_template): it ships as a complete working
placeholder task (maximize `x` in `[0, 1]`), so the suite passes before you
change anything. Verify standalone with `harbor trial start -p <dir>`, then
run it under tide.

## Anatomy of a task

Two containers: the agent's, and the judge's. All scoring lives with the
judge; the agent only ever sees scores come back over HTTP.

```
my-task/
├── task.toml            # stock Harbor config; network allows only the judge
├── instruction.md       # the problem + the submission protocol
├── environment/
│   ├── Dockerfile           # the AGENT's container (its data, no scoring)
│   ├── Dockerfile.judge     # the JUDGE's container
│   ├── docker-compose.yaml  # wires the judge in as a sidecar, sets $JUDGE_URL
│   ├── judge_server.py      # generic HTTP server; never edited per task
│   ├── score.py             # THE scoring rule: grade(path) → {"reward", "reason"}
│   ├── final.py             # optional final judge (hidden tests); see below
│   └── judge_config.json    # {"max_submissions": N, "min_interval_sec": s}
├── tests/
│   ├── test.sh · grade.py   # generic verifier: asks the judge for /final
│   └── grader_tests.json    # unit tests for score.py (and final.py)
└── solution/solve.sh        # reference solution; submits once, proves the pipeline
```

## The judge protocol

The agent gets `$JUDGE_URL` and a submission budget; everything else about
how it works is its own business (it may write its own local evaluator;
the objective is stated in the instruction):

| Request | Who calls it | What happens |
|---|---|---|
| `POST /submit` (body = the solution file) | the agent, at will | `score.py` grades it and records the result; over budget → 429 |
| `GET /status` | the agent | submissions used / remaining, best so far |
| `GET /final` | **403 on the agent port**: finalization is a verifier-only capability (see below) |  |

Finalization runs on a separate verifier port (`VERIFIER_PORT`, default
`PORT + 1`) behind a per-session token generated at startup. The token is
written to `{DATA_DIR}/.verifier_token`, inside the judge's own
filesystem, never in the agent's environment. The local executor reads it
from there; the container verifier fetches it via `GET /token` on the
verifier port (which the agent should not be able to reach; the network
policy keeps the agent on the agent port only).

| Request | Who calls it | What happens |
|---|---|---|
| `GET /final` | the verifier, once, at the end (verifier port + token) | the final verdict + the full submission log. **Terminal**: the first call locks the session; later submissions are refused, repeat calls return the cached verdict. |
| `GET /token` | the verifier (verifier port) | returns the per-session verifier token |

Trust follows from the topology: scoring code and data live only in the
judge image, the agent's network reaches only the judge's agent port
(`network_mode = "allowlist"`, `allowed_hosts = ["judge"]`), and every
number in the submission log was computed by the judge, which is why the
score-over-time curve is trusted, not self-reported.

### Artifact selection and lifecycle ordering

The judge owns artifact selection and the full lifecycle:

1. **Agent submits**: the agent POSTs candidate solutions to the agent
   port at will; the judge scores each and appends to the in-memory log.
2. **Agent stops**: the budget runs out or the agent exits.
3. **Verifier finalizes**: the trusted verifier (the local executor in
   `--local` mode, or `tests/grade.py` in containers) fetches the token
   from the verifier port, then calls `GET /final` on that port.
4. **Artifact frozen**: the judge selects the best submission by session
   score (`max(log, key=lambda e: (e["score"], -e["n"]))`), identifies it
   by its submission number, and reads the stored file
   `DATA_DIR/submission_{best_n}`. The artifact is already on disk;
   no content digest is needed because the judge never accepted a
   replacement for a logged submission.
5. **Final evaluation**: if `final.py` exists, it runs once on the
   frozen artifact; otherwise the best session score is the verdict.
6. **Session locked**: the verdict is cached; subsequent `/final` calls
   return the same object (safe for verifier retries); `/submit` is
   refused with 429.

The orchestrator (not the agent) owns steps 2-3; the judge owns steps 4-6.
The agent never observes the final evaluation or its result.

## The submission budget

`judge_config.json` is the task's anti-probing dial:

- **public metric, cheap scoring** (circle-packing, tsp-tour): a generous
  cap (say 1000): the budget exists mainly to bound judge compute;
- **expensive scoring** (string-compression runs the agent's program):
  a tighter cap;
- **metric with a secret**: keep the session feedback on public data and
  put the secret in the **final judge** (next section); then the budget
  doesn't need to carry the secrecy burden at all.

## The final judge (`final.py`, optional)

Same signature as `score.py`, run exactly once, on the best submission,
when the verifier finalizes. This is where hidden tests live: held-out
data, stricter checks, anything the session score must not leak.
[symbolic-regression](../../tasks/autoresearch/symbolic-regression) is the
reference: the session scores on training points; the final judge scores
once on held-out points, so no submission budget can be spent probing
them. Without `final.py`, the final verdict is simply the best session
score.

## The scoring contract

`score.py` (and `final.py`) expose one function:

```python
def grade(artifact: Path | None) -> dict:
    # {"reward": float, "reason": str}; invalid input → 0.0 with a reason
```

Rules: recompute everything from the submitted file, never trust anything
inside it; validate conservatively (exact arithmetic where floats can be
gamed; reject, don't round); malformed input scores `0.0` with a reason,
never an exception. Data files sit next to the script and are read via
`Path(__file__).parent`, so the same file works in the judge image and in
`--local` runs.

## Testing your task: `tests/grader_tests.json`

Each case is one sentence: *this solution must score this reward,
because…* Write one case for your reference solution and one for **each
rule your scorer enforces** (expected reward `0.0`). The template's file:

```json
{
  "solve_sh_scores": 0.5,
  "cases": [
    {"solution": {"x": 0.5}, "reward": 0.5, "why": "the reference solution scores exactly this"},
    {"solution": {"x": 1.5}, "reward": 0.0, "why": "out-of-bounds values must be rejected"},
    {"solution": {"nonsense": true}, "reward": 0.0, "why": "malformed input must score zero, not crash"}
  ]
}
```

- `cases` exercise `score.py` offline, in milliseconds, on every CI run;
  add `final_cases` (same shape) when the task has a final judge.
- `solve_sh_scores` drives the containerized E2E gate: what the reference
  solution must earn end to end, either a number or `{"min": …, "max": …}`
  where the live run legitimately varies.
- Optional per-case `"tolerance"` for float comparison (default 1e-9).

`pytest tests/test_task_suite.py` picks up any folder with this file
automatically. In containers, `--agent oracle` must reproduce
`solve_sh_scores` (the E2E gate) and `--agent nop` must score 0; if it
doesn't, the environment leaks the answer.

## Network policy

The default is the tightest thing that still works: the agent may reach
the judge and nothing else.

```toml
[environment]
network_mode = "allowlist"
allowed_hosts = ["judge"]

[agent]                            # optional phase override, e.g. for
network_mode = "allowlist"         # in-container LLM loops
allowed_hosts = ["judge", "api.openai.com"]
```

Never give the agent open internet on a task whose answers can be looked
up.

## A GPU task (kernels, CUDA, ML workloads)

A GPU task is a plain Harbor task with two extra pieces of configuration;
tide adds nothing:

1. Declare the requirement in `task.toml`; Harbor's schema validates it and
   Harbor's cloud backends (Modal, Beam, GKE, SkyPilot, Daytona, …) honor it
   natively:

   ```toml
   [environment]
   gpus = 1
   ```

2. For local Docker, GPU access is a standard compose device reservation in
   the task's `environment/docker-compose.yaml` (which the judge sidecar
   already uses), and needs the NVIDIA Container Toolkit on the host:

   ```yaml
   services:
     main:
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: all
                 capabilities: [gpu]
   ```

Give the **judge** service the reservation instead (or as well) when
scoring itself needs the GPU, e.g. re-timing kernels trustably. One
caveat for kernel-timing tasks: wall-clock speedups measured on
shared/heterogeneous hosts are noisy. Prefer scoring against a reference
implementation run in the same container, same session (relative speedup),
and record the GPU model as a tag so curves never mix hardware.

## A benchmark converter

A converter turns a published external format into a folder of task dirs.
Converters live beside the benchmark they maintain and depend only on its
published format, keeping benchmark-specific tooling out of tide's runtime
package. The reference implementation is `tasks/edgebench/convert.py`; its
tests pin the converter to unmodified published spec files; do the same for
any new converter: check one real spec into `tests/fixtures/` and validate
the emitted task under Harbor's `TaskConfig`.
