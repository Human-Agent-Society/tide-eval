# Glossary

Every term tide uses, in one place. Terms link to the page that owns them.

## Tasks and runs

| Term | Meaning |
|---|---|
| task | A stock Harbor task directory: `task.toml`, `instruction.md`, `environment/`, `tests/`, and a reference `solution/`. |
| episode | One run of one task under one agent; tide's unit of measurement. Equals one Harbor trial. |
| trial | Harbor's name for the same thing. Every episode's `uri` points at its trial directory, so results stay auditable. |
| agent, harness | Whatever does the work inside the task container: `claude-code`, `codex`, your own `BaseAgent`, or a plain script. See [running agents](running-agents.md). |
| oracle | Harbor's built-in agent that runs a task's reference `solution/`. Used to prove a task's pipeline end to end. |
| mode | Which kind of learning is being measured: autoresearch (within one problem) or continual learning (across a stream). See [design](design.md). |

## Scoring

| Term | Meaning |
|---|---|
| judge | In autoresearch tasks, the HTTP sidecar that holds all scoring code and data and scores every submission. The agent can reach it and nothing else. |
| submission | One candidate solution POSTed to the judge. Each task caps how many are allowed. |
| final judge | An optional `final.py` on the judge with hidden tests. Runs once, on the best submission, and locks the session. |
| verifier | Harbor's scoring step at the end of a trial: for judge tasks it asks the judge for the final verdict; for pass/fail tasks it runs the task's `tests/`. |
| reward | The trusted score of an episode, as reported by the verifier. |
| trace | Untrusted per-submission score rows stored next to the trusted episode row; the raw material of the anytime curve. |
| budget | What an episode may spend: time, evals, tokens, or cost. Set on the run, delivered as `TIDE_*` env vars, recorded as `budget_*` tags with actuals in `used_*` columns. See [budgets](get-started.md#budgets). |

## Results

| Term | Meaning |
|---|---|
| Lab | A directory holding the results store; `Lab.run` executes one episode into it. See [get started](get-started.md#the-python-api). |
| store | The append-only SQLite table behind a Lab. Two row kinds: `episode` and `trace`. |
| tags | Free-form dimensions on every row (model, suite, budget, stream). There is no fixed schema; metrics document the columns they expect. |
| key | An episode's stable id, derived from (task, agent, tags, overrides) or passed explicitly. A key that already has a row is skipped, which is how re-running resumes. |

## Streams

| Term | Meaning |
|---|---|
| stream | An ordered task list run under one agent with a state directory carried between tasks. See [streams](get-started.md#streams). |
| position | An episode's index within its stream, recorded as a tag. |
| state directory | The carried directory, mounted into every task's container as `$TIDE_STATE_DIR`. The agent writes whatever it wants its future self to know; tide never reads it. |
| snapshot | The state directory saved after each position. The next position starts from it, which makes starting states deterministic and resume clean. |
| variant | A digest of a stream's setup (agent, tags, budget, overrides). The same stream name under two setups keeps separate state and keys. |
