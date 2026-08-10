# Authoring tasks & benchmarks

Tasks are **100% stock Harbor tasks** — every committed task is validated
against Harbor's `TaskConfig` schema by `tests/test_task_suite.py`. tide
adds conventions *around* the format, never fields inside it. Start from
[`tasks/_template`](../../tasks/_template) (recommended), verify standalone
with `harbor trial start -p <dir>`, then run it under tide.

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
│   └── vectors.json   #   test vectors for the grader (oracle + cheat cases)
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
from the finished agent container, and grades them in a fresh one. The two
scripts usually share their math (the exemplar duplicates it deliberately,
with the private side at stricter tolerance).

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
   the untrusted progress curve — and `metrics.anytime` does the rest.

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

## Testing your task: `tests/vectors.json`

`vectors.json` holds the grader's test vectors: one **oracle case** (a
known-good artifact and the exact reward it must earn) and a set of
**cheat cases** — adversarial artifacts each embodying one way to fake the
score (a constraint violation, a float-epsilon exploit, a forged
self-reported score). Each cheat case must grade **exactly 0.0, with a
reason**; the suite re-checks them on every CI run. The exemplar's real file:
[circle-packing/tests/vectors.json](../../tasks/autoresearch/circle-packing/tests/vectors.json).

```jsonc
{
  "oracle": {
    "artifact": { "circles": [[0.25, 0.25, 0.25], ...] },  // known-good solution
    "reward": 0.75          // exact (± "tolerance"); or "reward_min"/"reward_max";
  },                        // "live_min"/"live_max" for the containerized E2E gate
  "cheats": [
    { "name": "overlap",      "artifact": { "circles": [...] } },
    { "name": "forged_claim", "artifact": { "circles": [...], "claimed_score": 999.0 } }
  ]
}
```

Any task folder with a `vectors.json` is picked up by
`pytest tests/test_task_suite.py` automatically: oracle scores its declared
reward, every cheat scores 0.0, missing artifact scores 0.0, `task.toml`
validates under Harbor's schema. Then `--agent oracle` in real containers
must reproduce the score (the E2E gate), and `--agent nop` must score 0 —
if it doesn't, the environment is leaking the answer.

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
