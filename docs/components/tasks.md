# Authoring tasks & benchmarks

Tasks are **100% stock Harbor tasks** — that promise is enforced by a test
(`test_exemplar_task_is_valid_stock_harbor`). tide adds conventions *around*
the format, never fields inside it. Scaffold with `harbor task init`, verify
standalone with `harbor trial start -p <dir>`, then run it under tide.

## A plain episodic task

```
my-task/
├── task.toml          # timeouts, resources, network policy
├── instruction.md     # what the agent sees (the ONLY thing it sees)
├── environment/       # Dockerfile — the agent's world
├── tests/             # test.sh → writes /logs/verifier/reward.{txt,json}
└── solution/          # solve.sh — proves the task is solvable (oracle)
```

## An autoresearch task (the four conventions)

Reference implementation: [`tasks/autoresearch/circle-packing`](../../tasks/autoresearch/circle-packing).

1. **Public scorer in the image** (`environment/scorer.py`). The agent
   self-evaluates freely. Deliberately unisolated: *things you don't trust
   don't need walls* — tampering with it only sends the agent up the wrong
   gradient.
2. **The wall**: in `task.toml`,
   ```toml
   artifacts = ["/app/best/solution.json", "/app/best/score_log.jsonl"]
   [verifier]
   environment_mode = "separate"
   ```
   Grading runs in a fresh container that receives *only* declared artifacts;
   `tests/grade.py` recomputes everything (exact rational arithmetic in the
   exemplar — a 5e-9 overlap scores zero), and **never reads agent-claimed
   scores**. In separate mode `tests/` is the verifier's build context, so it
   ships its own `Dockerfile` that copies itself to `/tests`.
3. **Timeout = budget.** The instruction mandates atomic best-so-far writes
   (temp file + rename); Harbor grades after a timeout, so a deadline kill
   still scores the best snapshot.
4. **Score log**: the agent appends `{"t": <sec>, "score": <x>}` to
   `score_log.jsonl` in the artifact dir. tide ingests it as `trace` rows —
   the untrusted progress curve — and `metrics.anytime` does the rest.

Keep the three test agents in rotation: **oracle** (must score its known
value — pipeline proof), **nop** (must score 0 — leakage baseline), and a
**cheater** (tampered scorer + forged log — must not move the trusted score;
the exemplar's grader test does exactly this).

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
