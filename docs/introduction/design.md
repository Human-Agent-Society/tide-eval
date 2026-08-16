# Design

How tide evaluates autoresearch and continual-learning task streams, and
why it is shaped the way it is.
For the module-by-module reference see the [API](../api/lab.md); for
integrating an agent see [integration.md](../guides/integration.md).

## What an autoresearch task is

An autoresearch task is an open-ended optimization problem with three
properties that break a pass/fail harness:

- **continuous score** — "how good", not "did it pass";
- **a budget, not a finish line** — the agent works until the budget runs
  out (time, evals, tokens, or cost — see
  [budget](../api/budget.md)), and being stopped at the
  deadline is a normal ending that must still produce a grade;
- **iteration in the loop** — the agent tries many candidates and needs
  feedback on them, and any feedback machinery it can reach it can also
  tamper with.

Everything in tide follows from taking those three properties seriously.

## The trust model: the judge owns all scoring

Two containers. The agent works in one; the judge — an HTTP server holding
every line of scoring code and data — runs in the other. The agent's
network reaches the judge and nothing else.

```mermaid
sequenceDiagram
    autonumber
    participant A as agent container
    participant J as judge container<br/>(all scoring lives here)
    participant V as verifier
    participant S as results store

    loop until the time budget or the submission budget runs out
        A->>J: POST /submit (a solution file)
        J->>J: score.py grades it · appends to the log
        J-->>A: {score, best, remaining}
    end
    Note over A: deadline — a normal ending
    V->>J: GET /final (terminal: locks the session)
    J->>J: final.py on the best submission<br/>(hidden tests, once) — or best session score
    J-->>V: {reward, reason, submission log}
    V->>S: 1 trusted episode row + the log as trace rows
```

Three decisions carry the model:

- **One scoring implementation, judge-side.** `score.py` grades every
  submission; the agent sees only scores coming back. There is nothing on
  the agent's side to keep honest, because there is nothing on the agent's
  side at all — it may build its own local evaluator for its inner loop
  (the objective is in the instruction), and tide neither requires nor
  trusts that.
- **The submission budget** (`judge_config.json`) bounds judge compute and
  information leakage — the same dial Kaggle turns with daily submission
  limits. Refused submissions are never recorded.
- **The final judge is terminal.** `final.py` (optional) holds hidden
  tests — held-out data, stricter checks — and runs exactly once, on the
  best submission, when the verifier calls `GET /final`. That call locks
  the session: later submissions are refused and repeat calls return the
  cached verdict, so an agent that peeks early ends its own run.
   [symbolic-regression](../../tasks/autoresearch/symbolic-regression) is the
  reference: session feedback on training points, final grade on held-out
  points that no submission budget can probe.

Trust is tested, not asserted: `tests/test_task_suite.py` feeds every
scorer its task's cheat cases — out-of-bounds values, float-epsilon
exploits, forged fields — and requires exactly zero for each; the E2E
workflow runs the oracle agent (Harbor's built-in agent that executes a
task's reference solution) through real containers and requires its exact
known score.

## The curve is trusted

Because every submission is judge-scored, the submission log — ingested
as `trace` rows — is a **trusted** score-over-time record. The anytime curve, its
AUC, time-to-threshold, and improvement counts are queries over real
measurements, not the agent's claims. This is the payoff of paying one
judge evaluation per submission, and the submission budget is what keeps
that price bounded.

## The data model

One append-only store (SQLite, one per `Lab` directory), one row shape,
two kinds:

| kind | one row per | key shape | source |
|---|---|---|---|
| `episode` | one task run (= one Harbor trial) | `<key>` | the judge's final verdict |
| `trace` | one submission | `<key>#t<i>` | the judge's submission log |

Three load-bearing decisions:

- **Re-running resumes.** Every episode gets a stable ID derived from
  (task, agent, tags, overrides) — or supplied explicitly. An ID that
  already has a row is skipped, so running the same script again picks up
  where it crashed.
  There is no daemon and no job state: persistence lives in the data.
  Resume is deliberately episode-granular: a half-finished 12-hour episode
  starts over, because a run stitched together from checkpoints is not the
  same measurement as one clean budget — and would not be comparable to
  anyone else's.
- **Tags are the schema.** Budgets, attempts, models, suites are free-form
  tags; a budget-scaling curve and a model comparison are both pivots over
  `lab.df()`. Metrics declare the columns they expect; nothing fixes a
  result format up front.
- **Raw scores in the store, normalization at query time.** Re-anchoring a
  0–100 scale never requires re-running anything.

Every row's `uri` points at the Harbor trial directory that produced it —
logs, the judge's submission log, the verifier's output — so any number in any
table can be audited back to its evidence.

## The second mode: task streams

Autoresearch measures learning *within* one episode. A
[**stream**](../api/streams.md) measures it *across* episodes: an ordered
sequence of stock Harbor tasks run under one agent, with a state directory
carried from episode to episode — the streaming setting of
[AgentStream](https://arxiv.org/abs/2608.00155). Terminal-bench-style
pass/fail tasks work as-is (a pass is just a 0-or-1 score); AgentStream's
*isolated* scenario is a plain `lab.run` sweep, and its *sequential* and
*interleaved* scenarios are just how you order a `Stream`'s task list.

Each position is one ordinary episode — one Harbor trial, one container,
one trusted row. The only thing connecting positions is the state
directory, bind-mounted into the agent's container as `$TIDE_STATE_DIR`,
where the agent keeps whatever it wants to remember: memory files, a
skill library, an evolved harness. Whether carrying that state helps is
the measurement — the learning curve over positions, transfer against the
isolated control arm, forgetting on revisited tasks.

Three decisions carry the mode:

- **Deterministic starting state.** Before an episode runs, the live state
  directory is reset from the previous position's snapshot; after it runs,
  the ending state is snapshotted. Every episode's input is reproducible
  and auditable no matter what crashed in between.
- **Resume with honest history.** Recorded positions are skipped as
  always, and a position's key covers the task list up to that position:
  appending tasks extends a finished stream, while editing an earlier
  position re-runs everything after it — a stream is one measurement, and
  a changed history invalidates what followed.
- **The trust model is unchanged.** The state is agent-authored and
  untrusted; no judge or verifier ever sees it, so it can influence only
  the agent's own future behavior.

Episode rows from a stream land in the same table, tagged `stream` and
`position`; the continual-learning metrics are queries like every other
metric.

## Why Harbor, as a library

Harbor already solved single-trial evaluation well: task format, container
backends, sidecar wiring, agent adapters. tide imports it as a library
and never touches its CLI — a fork would lose the upstream task ecosystem;
a wrapper keeps it. Tasks remain 100% stock Harbor tasks (enforced by
test): every task here also runs standalone under `harbor trial start`, and
Harbor registry ids run here unchanged. tide's own surface stays small on
purpose — roughly: `Lab` (orchestration + store), an `Executor` protocol
with Harbor and local implementations, submission-log ingestion, and pure-pandas
metrics. See the [API reference](../api/lab.md) for each module's invariants.

## Extensibility

The frozen interface is deliberately minimal — `Lab.run`'s signature and
the store schema (columns may be added, never changed) — and the extension
points are structural rather than speculative:

- `Row.kind` is an open string: a future regime adds new kinds with their
  own key shapes, no schema change;
- `Executor` is a one-method protocol (`execute(spec) → result`): new
  backends (SSH, cloud batch, a simulator, an external-ground-truth
  observer) never touch the core;
- metrics are standalone functions over the one table: a new metric is one
  function plus a docstring declaring its expected columns.

This is how [streams](../api/streams.md) landed — `Stream` sequences
ordinary episodes around the same store, the executors gained one shared
override, and the metrics are three new functions — and it is how live
infinite-horizon tasks would land too. What is actually on deck lives in
the [roadmap issue](https://github.com/Human-Agent-Society/tide-eval/issues/19).

## Design rules

1. **One frozen interface.** `Lab.run`'s signature and the store schema.
2. **Tasks stay stock Harbor.** No tide-specific fields in `task.toml`, ever.
3. **The judge owns all scoring.** The agent's side carries no scoring
   machinery; every anti-cheating claim ships with tests that actually cheat.
4. **Persistence lives in data, not processes.** No daemon; re-running any
   crashed script resumes it.
5. **Abstractions are earned.** A helper enters the library when it has
   repeated in at least two real scripts, not before.
