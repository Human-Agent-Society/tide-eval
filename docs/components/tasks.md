# Authoring tasks & benchmarks

Tasks are **100% stock Harbor tasks** — every committed task is validated
against Harbor's `TaskConfig` schema by `tests/test_task_suite.py`. tide
adds conventions *around* the format, never fields inside it. Start from
[`tasks/_template`](../../tasks/_template) — it ships as a complete working
placeholder task (maximize `x` in `[0, 1]`), so the suite passes before you
change anything. Verify standalone with `harbor trial start -p <dir>`, then
run it under tide.

## Anatomy of a task

Every file belongs to one of two evaluations — the agent's own (public) or
the benchmark's (private):

```
my-task/
├── task.toml          # config: budget, resources, network policy, declared artifacts
├── instruction.md     # the problem statement (the ONLY thing the agent is told)
├── environment/       # agent container — built from this Dockerfile
│   └── scorer.py      #   PUBLIC eval: the scorer the agent iterates against
├── tests/             # verifier container — its own Dockerfile, built separately
│   ├── test.sh        #   entrypoint: runs grade.py
│   ├── grade.py       #   PRIVATE eval: the trusted grader
│   └── grader_tests.json   #   unit tests for grade.py (one good case + cheat cases)
└── solution/          # reference solution — the oracle agent runs solve.sh
```

## Public vs private evaluation

The split is the same one Kaggle users know as public vs private
leaderboard: the score you can query freely is not the score that counts.

| | Public scorer | Private verifier |
|---|---|---|
| file | `environment/scorer.py` | `tests/grade.py` |
| built into | the **agent's** container image | a **separate** verifier image (`tests/` is its own build context) |
| runs | whenever the agent calls it — unlimited | once, in a fresh container, after the budget ends |
| sees | everything in the agent container | **only** the artifacts declared in `task.toml` |
| output | a score on stdout; the agent logs it to `score_log.jsonl` → `trace` rows | `/logs/verifier/reward.json` → the `episode` row |
| trusted | no — the agent can tamper with it; it exists as search feedback | yes — this is the benchmark number |

Setup: declaring `environment_mode = "separate"` under `[verifier]` plus an
`artifacts = [...]` list in `task.toml` is what creates the isolation —
Harbor builds `tests/` as its own image, collects only the declared files
from the finished agent container, and grades them in a fresh one.

**You write the scoring twice, on purpose.** The two files live in
different build contexts and cannot import each other, and the private
side should usually be stricter anyway (exact arithmetic, held-out data,
conservative rejection). If they drift apart, scores stay correct — the
public side only misleads the agent's own search. The
[template](../../tasks/_template) demonstrates the pattern and documents
the single-source alternative.

## An autoresearch task (the four conventions)

Reference implementation: [`tasks/autoresearch/circle-packing`](../../tasks/autoresearch/circle-packing).

1. **Public scorer in the image** (`environment/scorer.py`). The agent
   self-evaluates freely. Deliberately unprotected: nothing it produces is
   trusted, so tampering with it only misleads the agent's own search.
2. **Verifier isolation**: in `task.toml`,
   ```toml
   artifacts = ["/app/best/solution.json", "/app/best/score_log.jsonl"]
   [verifier]
   environment_mode = "separate"
   ```
   `tests/grade.py` recomputes everything from the declared artifacts alone
   (exact rational arithmetic in the exemplar — a 5e-9 overlap scores zero)
   and **never reads agent-claimed scores**.
3. **Timeout = budget.** The instruction mandates atomic best-so-far writes
   (temp file + rename); Harbor grades after a timeout, so a deadline kill
   still scores the best snapshot.
4. **Score log**: the agent appends `{"t": <sec>, "score": <x>}` to
   `score_log.jsonl` in the artifact dir. tide ingests it as `trace` rows —
   the agent's own (untrusted) scores — and `metrics.anytime` does the rest.

## The grader contract

`tests/test.sh` runs `tests/grade.py` in the verifier container:

```python
def grade(artifact: Path | None) -> dict:
    # {"reward": float, "reason": str}; artifact None → reward 0.0
```

Three rules ([template](../../tasks/_template/tests/grade.py)): recompute
everything from the artifact, **never read agent-claimed scores**; validate
conservatively (exact arithmetic where floats can be gamed; reject, don't
round); missing/malformed artifact → `0.0` with a reason, never an
exception. The script writes `reward.json` (numbers only) and `reason.txt`
to `/logs/verifier/`.

## Unit-testing the grader: `tests/grader_tests.json`

Three questions, answered up front:

- **Is this a Harbor concept?** No. Harbor's own quality check is running
  the oracle agent in real containers — correct but slow, and it needs
  Docker. `grader_tests.json` is tide's fast path: it unit-tests
  `grade.py` directly, in milliseconds, offline, on every CI run.
- **Do you need it?** To *run* a task — no; tasks without it work fine
  (none of the external catalogs have one). To merge a **first-party**
  task — yes, and the suite enforces that. Autoresearch graders hand out
  continuous scores computed from agent-written files: one lenient check
  is free points, and an agent with an hours-long budget will find it.
- **How do you write it?** A ten-minute recipe:
  1. take a solution you know is correct — that's the `oracle` entry;
     write down the exact reward `grade.py` must give it;
  2. for **each rule your grader enforces**, write one artifact that
     breaks it — those are the `cheats`; each must score exactly `0.0`
     with a reason;
  3. run `pytest tests/test_task_suite.py` — any folder with this file is
     picked up automatically.

The template's complete file, for the maximize-`x` task:

```json
{
  "oracle": {"artifact": {"x": 0.5}, "reward": 0.5},
  "cheats": [
    {"name": "out_of_bounds", "artifact": {"x": 1.5}},
    {"name": "epsilon_over", "artifact": {"x": 1.0000000001}},
    {"name": "forged_claim", "artifact": {"x": 0.0, "claimed_score": 999.0}},
    {"name": "malformed", "artifact": {"nonsense": true}}
  ]
}
```

Advanced knobs, only when you need them: `"tolerance"` for float
comparison against the oracle reward; `"reward_min"`/`"reward_max"` when
the legitimate reward is a range; `"live_min"`/`"live_max"` when the
*containerized* oracle run legitimately varies (compression ratios across
zlib builds) — used only by the E2E gate.

The container-level checks stay Harbor-native and complement this file:
`--agent oracle` must reproduce the score end to end (the E2E gate), and
`--agent nop` must score 0 — if it doesn't, the environment leaks the
answer.

## Network policy

Harbor's network policy is per-phase, set in `task.toml`:

```toml
[environment]
network_mode = "no-network"        # baseline: "public" | "no-network" | "allowlist"

[agent]                            # optional phase override, same fields
network_mode = "allowlist"
allowed_hosts = ["api.openai.com", "api.anthropic.com"]

[verifier]                         # keep the verifier offline — always
network_mode = "no-network"
```

Guidance: default the environment to `no-network` (an offline task can't
look up known solutions); when agents need an LLM API *from inside* the
container, open an `allowlist` on the `[agent]` phase rather than making
the whole environment public; never give the verifier network access.

## A GPU task (kernels, CUDA, ML workloads)

A GPU task is a plain Harbor task with two extra pieces of configuration —
tide adds nothing:

1. Declare the requirement in `task.toml`; Harbor's schema validates it and
   Harbor's cloud backends (Modal, Beam, GKE, SkyPilot, Daytona, …) honor it
   natively:

   ```toml
   [environment]
   gpus = 1
   ```

2. For local Docker, Harbor merges a task-authored
   `environment/docker-compose.yaml` over its generated one (the agent's
   service is named `main`). GPU access is a standard compose device
   reservation, and needs the NVIDIA Container Toolkit on the host:

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

The same overlay mechanism composes with everything else — the vendored
FrontierCS kernel tasks (`tasks/frontier-cs/*gpu-kernel*`) use it to add a
separate judge sidecar with health checks. If the *verifier* needs the GPU
too (re-timing kernels trustably), give `tests/` its own Dockerfile with the
same reservation; in `separate` mode it is its own build context.

One honest caveat for kernel-timing tasks: wall-clock speedups measured on
shared/heterogeneous hosts are noisy. Prefer verifiers that grade against a
reference implementation run *in the same container, same session* (relative
speedup), and record the GPU model as a tag so curves never mix hardware.

## A benchmark converter

A converter turns a published external format into a folder of task dirs.
Converters depend **only on the
published format and tide's public types** — so they can't break anything.
The reference implementation is `tide/converters/edgebench.py`: the spec's
`work` half becomes `instruction.md` + `environment/`, its `judge` half
becomes `tests/` (their two-container judging maps onto the separate
verifier), `submit_paths` become declared artifacts, and budgets are run
parameters (`tags={"budget": h}` + `metrics.scaling`). Its tests pin the
converter to unmodified published spec files — do the same for any new
converter: check one real spec into `tests/fixtures/` and validate the
emitted task under Harbor's `TaskConfig`.
