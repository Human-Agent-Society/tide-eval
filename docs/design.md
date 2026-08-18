# Design

What tide evaluates, and why it is shaped that way.
For the practical pages see [get started](get-started.md) and
[running agents](running-agents.md).

tide is evaluation infrastructure for self-evolving agents: agents that
learn from signals produced during the run itself and keep what they
learned. Continual learning in the broad sense is the same idea, and the
narrow one, weight updates over a task sequence, is one case of it rather
than the whole of it. Adaptation that ends when the episode does is not
what tide measures, so in-context reasoning, a retry after an error, and
a test-time search all fall outside it.

The form the learning persists in is up to the method, and tide never
trains anything itself: a method that updates weights runs its own loop,
and tide measures the result. tide provides the two task regimes where
persistence shows up, and the measurements that show whether anything
did. The regime is the shape of the work, not the mechanism: an
autoresearch run whose agent evolves its own harness is continual
learning inside one problem, and a stream whose agent carries nothing is
not continual learning at all, which is the stateless baseline
`metrics.transfer` compares against.

## The two regimes

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
- **positions are connected only by the carried state**, mounted into
  the agent's container as `$TIDE_STATE_DIR`, where the agent keeps
  whatever it wants to remember;
- **the measurement is the difference state makes**: the learning curve
  over positions, transfer against an isolated baseline, forgetting on
  revisited tasks. AgentStream's sequential and interleaved scenarios map
  onto target order and a seeded shuffle; its isolated scenario is one
  stream per benchmark, with no state shared between them. The stateless
  baseline `metrics.transfer` subtracts is a plain `lab.run` sweep, which
  is a different thing again.


## Trust: scoring stays out of the agent's hands

Both regimes share one rule: the agent can never reach the code or data
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

In streams, Harbor's verifier grades pass/fail tasks after the episode,
and tasks with hidden state reuse the judge pattern: a sidecar the agent
reaches only over HTTP holds what must stay out of reach (the metered
database and the poker deck in
[CL-Bench](https://github.com/Human-Agent-Society/tide-eval/tree/main/tasks/continual-learning/cl-bench), which also enforces
their budgets). The carried state directory is the one new surface,
agent-written and untrusted: no judge or verifier ever sees it, so it can
only influence the agent's own future behavior.

Trust is tested, not asserted: `tests/test_task_suite.py` feeds every
scorer its task's cheat cases (out-of-bounds values, float-epsilon
exploits, forged fields) and requires exactly zero for each; the E2E
workflow runs the oracle agent (Harbor's built-in agent that executes a
task's reference solution) through real containers and requires its exact
known score.

Every submission is therefore judge-scored, which is what makes the
submission log a trusted score-over-time record rather than the agent's
claims about itself. It costs one judge evaluation per submission, and the
submission budget bounds that. In streams each position's reward is
verifier-graded, so the learning curve is trusted point by point.

## The data model

One append-only store (SQLite, one per `Lab` directory), one row shape,
two kinds:

| kind | one row per | key shape | source |
|---|---|---|---|
| `episode` | one task run (= one Harbor trial) | `<key>` | the verifier's verdict (for judge tasks, the judge's final grade) |
| `trace` | one submission | `<key>#t<i>` | the judge's submission log |

Three decisions:

- **Re-running resumes.** Every episode gets a stable ID derived from
  (task, agent, tags, overrides), or supplied explicitly. An ID that
  already has a row is skipped, so running the same script again picks up
  where it crashed.
  There is no daemon and no job state: persistence lives in the data.
  Resume is episode-granular: a half-finished 12-hour episode starts
  over, because a run stitched together from checkpoints is not the same
  measurement as one clean budget, and not comparable to anyone else's.
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
  what crashed in between, and every step's memory stays auditable.
- **Resume with stable history.** Recorded positions are skipped as
  always, and a position's key covers the task list up to that position:
  appending tasks extends a finished stream, editing an earlier position
  re-runs everything after it. Each snapshot is named by that same
  prefix, so a snapshot is only ever reused by a stream whose history up
  to that point matches, and two streams sharing a name cannot inherit
  each other's memory.

Episode rows from a stream land in the same table, tagged `stream` and
`position`; the continual-learning metrics are queries like every other
metric.
