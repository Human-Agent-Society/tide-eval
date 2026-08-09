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

Reference implementation: [`examples/tasks/circle-packing-mini`](../../examples/tasks/circle-packing-mini).

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

## A benchmark converter

A converter turns a published external format into a folder of task dirs
(plus an ordered manifest for streams). Converters depend **only on the
published format and tide's public types** — so they can't break anything.
The reference implementation is `tide/converters/edgebench.py`: the spec's
`work` half becomes `instruction.md` + `environment/`, its `judge` half
becomes `tests/` (their two-container judging maps onto the separate
verifier), `submit_paths` become declared artifacts, and budgets are run
parameters (`tags={"budget": h}` + `metrics.scaling`). Its tests pin the
converter to unmodified published spec files — do the same for any new
converter: check one real spec into `tests/fixtures/` and validate the
emitted task under Harbor's `TaskConfig`.

## A stream benchmark

Ship (a) tasks or probes, (b) an ordered manifest (a JSON list is fine),
(c) the protocol script. The ingest-then-probe conversion for context-
learning corpora is in [`examples/stream_cl.py`](../../examples/stream_cl.py):
learn = ingest into `StateDir`; probe = ask *without* the context, both
`stateful` and `fresh` arms; `metrics.gain` and `metrics.internalization`
read the result.

## Live tasks

For tasks with no natural end (trading, ops), the mapping is:
**infinite horizon = an unbounded stream of measurement windows.**

- A window (day/week — or event-triggered: a market resolving, a drawdown
  threshold) is one episode; `key` = the window id, which makes week-long
  runs crash-resumable for free.
- The verifier **observes external ground truth** (e.g. the exchange's
  account API) instead of recomputing an artifact — same wall, different
  source; the agent can't forge the exchange's ledger.
- No reruns exist, so comparisons need **contemporaneous controls**: run all
  arms in the same window, tagged. The nop agent means *hold*, so
  `score − nop = alpha`.
- Individual trades are actions *inside* an episode: log them through the
  score-log path (verifier overwrites with the exchange's fill history) and
  per-trade analytics become queries — no per-trade episodes.
