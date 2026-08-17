# Design

What tide evaluates, and why it is shaped the way it is.
For the practical pages see [get started](get-started.md) and
[running agents](running-agents.md).

tide evaluates learning from inference-time signals: feedback produced
during the run itself. Its two modes measure two different things
improving. In **autoresearch**, what improves is the solution: the agent
iterates on one open-ended problem against an evaluator. In **continual
learning**, what improves is the agent: it carries state across a stream
of tasks, and the question is whether later tasks go better for it.

## What the two modes measure

An autoresearch task is an open-ended optimization problem with three
properties that break a pass/fail harness:

- **continuous score**: "how good", not "did it pass";
- **a budget, not a finish line**: the agent works until the budget runs
  out (time, evals, tokens, or cost; see [budgets](get-started.md#budgets)),
  and being stopped at the deadline is a normal ending that must still
  produce a grade;
- **iteration in the loop**: the agent tries many candidates and needs
  feedback on them, and any feedback machinery it can reach it can also
  tamper with.

A [stream](get-started.md#streams) is an ordered sequence of stock Harbor
tasks run under one agent, with a state directory carried from task to
task: the streaming setting of
[AgentStream](https://arxiv.org/abs/2608.00155). Its defining properties:

- **each position is one ordinary episode**: one Harbor trial, one
  container, one trusted row; pass/fail tasks work as-is (a pass is a
  0-or-1 score);
- **the only thing connecting positions is the carried state**, mounted
  into the agent's container as `$TIDE_STATE_DIR`, where the agent keeps
  whatever it wants to remember;
- **the measurement is the difference state makes**: the learning curve
  over positions, transfer against an isolated baseline, forgetting on
  revisited tasks. AgentStream's isolated, sequential, and interleaved
  scenarios map onto a plain `lab.run` sweep, target order, and a seeded
  shuffle.

Everything in tide follows from taking these properties seriously.

## Trust: scoring stays out of the agent's hands

Both modes share one rule: the agent can never reach the code or data
that grades it.

In autoresearch, scoring lives in a **judge**: an HTTP server in its own
container holding every line of scoring code and data. The agent's
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
    Note over A: deadline (a normal ending)
    V->>J: GET /final (terminal: locks the session)
    J->>J: final.py on the best submission<br/>(hidden tests, once), or best session score
    J-->>V: {reward, reason, submission log}
    V->>S: 1 trusted episode row + the log as trace rows
```

Three decisions carry the judge model:

- **One scoring implementation, judge-side.** `score.py` grades every
  submission; the agent sees only scores coming back. No scoring
  machinery exists on the agent's side to protect. The agent may build
  its own local evaluator for its inner loop (the objective is in the
  instruction), and tide neither requires nor trusts that.
- **The submission budget** (`judge_config.json`) bounds judge compute and
  information leakage, the same mechanism as Kaggle's daily submission
  limits. Refused submissions are never recorded.
- **The final judge is terminal.** `final.py` (optional) holds hidden
  tests (held-out data, stricter checks) and runs exactly once, on the
  best submission, when the verifier calls `GET /final`. That call locks
  the session: later submissions are refused and repeat calls return the
  cached verdict, so an agent that calls it early terminates its own
  session.
  [symbolic-regression](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/autoresearch/first-party/symbolic-regression)
  is the reference: session feedback on training points, final grade on
  held-out points that no submission budget can probe.

In streams, pass/fail tasks are graded by Harbor's verifier after the
episode, and tasks with hidden state reuse the judge pattern: a sidecar
the agent reaches only over HTTP holds what must stay out of reach (the
metered database and the poker deck in
[CL-Bench](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/continual-learning/cl-bench), which also enforces
their budgets). The carried state directory is the one new surface, and
it is agent-written and untrusted: no judge or verifier ever sees it, so
it can only influence the agent's own future behavior.

Trust is tested, not asserted: `tests/test_task_suite.py` feeds every
scorer its task's cheat cases (out-of-bounds values, float-epsilon
exploits, forged fields) and requires exactly zero for each; the E2E
workflow runs the oracle agent (Harbor's built-in agent that executes a
task's reference solution) through real containers and requires its exact
known score.

## The curve is trusted

Because every submission is judge-scored, the submission log, ingested
as `trace` rows, is a **trusted** score-over-time record. The anytime curve, its
AUC, time-to-threshold, and improvement counts are queries over real
measurements, not the agent's claims. This is the payoff of paying one
judge evaluation per submission, and the submission budget is what keeps
that price bounded. Streams get the equivalent for free: each position's
reward is verifier-graded, so the learning curve is trusted point by
point.

## The data model

One append-only store (SQLite, one per `Lab` directory), one row shape,
two kinds:

| kind | one row per | key shape | source |
|---|---|---|---|
| `episode` | one task run (= one Harbor trial) | `<key>` | the verifier's verdict (for judge tasks, the judge's final grade) |
| `trace` | one submission | `<key>#t<i>` | the judge's submission log |

Three load-bearing decisions:

- **Re-running resumes.** Every episode gets a stable ID derived from
  (task, agent, tags, overrides), or supplied explicitly. An ID that
  already has a row is skipped, so running the same script again picks up
  where it crashed.
  There is no daemon and no job state: persistence lives in the data.
  Resume is deliberately episode-granular: a half-finished 12-hour episode
  starts over, because a run stitched together from checkpoints is not the
  same measurement as one clean budget, and would not be comparable to
  anyone else's.
- **Tags are the schema.** Budgets, attempts, models, suites, stream
  positions are free-form tags; a budget-scaling curve, a model
  comparison, and a learning curve are all pivots over `lab.df()`.
  Metrics declare the columns they expect; nothing fixes a result format
  up front.
- **Raw scores in the store, normalization at query time.** Re-anchoring a
  0-100 scale never requires re-running anything.

Every row's `uri` points at the Harbor trial directory that produced it
(logs, the judge's submission log, the verifier's output), so any number in any
table can be audited back to its evidence.

## How streams run

Two decisions make a stream one clean measurement rather than a loose
batch:

- **Deterministic starting state.** The live state directory is reset
  from the previous position's snapshot before every episode and
  snapshotted after, so each episode's input is reproducible no matter
  what crashed in between, and every step's memory can be audited later.
- **Resume with stable history.** Recorded positions are skipped as
  always, and a position's key covers the task list up to that position:
  appending tasks extends a finished stream, editing an earlier position
  re-runs everything after it.

Episode rows from a stream land in the same table, tagged `stream` and
`position`; the continual-learning metrics are queries like every other
metric.

## Why Harbor, as a library

Harbor already solved single-trial evaluation well: task format, container
backends, sidecar wiring, agent adapters. tide imports it as a library
and never touches its CLI: a fork would lose the upstream task ecosystem;
a wrapper keeps it. Tasks remain 100% stock Harbor tasks (enforced by
test): every task here also runs standalone under `harbor trial start`, and
Harbor registry ids run here unchanged. tide's own surface stays small on
purpose, roughly: `Lab` (orchestration + store), `Stream` (sequencing +
carried state), an `Executor` protocol with Harbor and local
implementations, submission-log ingestion, and pure-pandas metrics.

## Extensibility

The frozen interface is deliberately minimal, just `Lab.run`'s signature
and the store schema (columns may be added, never changed), and the extension
points are structural rather than speculative:

- `Row.kind` is an open string: a future regime adds new kinds with their
  own key shapes, no schema change;
- `Executor` is a one-method protocol (`execute(spec) → result`): new
  backends (SSH, cloud batch, a simulator, an external-ground-truth
  observer) never touch the core;
- metrics are standalone functions over the one table: a new metric is one
  function plus a docstring declaring its expected columns.

This is how [streams](get-started.md#streams) landed (`Stream` sequences
ordinary episodes around the same store, the executors gained one shared
override, and the metrics are three new functions), and it is how live
infinite-horizon tasks would land too. What is actually on deck lives in
the [roadmap issue](https://github.com/Human-Agent-Society/tide-eval/issues/19).

## Design rules

1. **One frozen interface.** `Lab.run`'s signature and the store schema.
2. **Tasks stay stock Harbor.** No tide-specific fields in `task.toml`, ever.
3. **Scoring stays out of the agent's hands.** Judge for autoresearch,
   verifier and sidecars for streams; every anti-cheating claim ships
   with tests that actually cheat.
4. **Persistence lives in data, not processes.** No daemon; re-running any
   crashed script resumes it.
5. **Abstractions are earned.** A helper enters the library when it has
   repeated in at least two real scripts, not before.
