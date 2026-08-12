# Get started

Zero to a real agent score on `autoresearch/circle-packing`, including the
two things that actually go wrong on a first run: agent authentication and
network egress. For the concepts behind the pipeline see
[design.md](design.md); for integrating your own method see
[integration.md](integration.md).

## Prerequisites

```bash
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
pip install -e ".[harbor]"     # container runs; plain -e . covers --local and the API
```

- **Docker** — tasks run in containers. One caveat: first-party tasks use an
  `allowlist` network policy, which Harbor enforces with an nftables egress
  sidecar. That needs a kernel with `CONFIG_NFT_FIB_INET`; Docker Desktop
  older than ~4.30 (linuxkit 5.15) doesn't have it and Harbor will refuse
  the run — see [Troubleshooting](#troubleshooting).
- **An agent login** — Harbor's installed agents run their CLI *inside* the
  task container and need credentials injected:
  - **codex**: `export OPENAI_API_KEY=...`, or reuse your local
    `codex login` session with `CODEX_FORCE_AUTH_JSON=1` (Harbor uploads
    `~/.codex/auth.json` into the container).
  - **claude-code**: `ANTHROPIC_API_KEY` (or its own login flow).

## Pick your depth

| Path | Command | What it proves |
|---|---|---|
| simulated | `python examples/quickstart.py` | the Lab API; scores are fake | 
| local | `tide run autoresearch/circle-packing --local --command "python examples/minimal_harness_search.py" --budget 0.01` | the *real* judge, no Docker, no isolation |
| containers | below | the real pipeline — this is what you report |

## Smoke test: the oracle

The `oracle` agent runs each task's reference `solution/` in-container. It
needs no keys and no network, so it isolates the plumbing:

```bash
tide run autoresearch/circle-packing --agent oracle
#   OK  circle-packing: {'reward': 0.75}     <- exactly 0.75, or something is broken
```

## Run codex for real

First-party tasks lock the agent's network down to the judge sidecar
(`allowed_hosts = ["judge"]` in `task.toml`). A container-brain agent needs
two kinds of egress on top of that:

1. **install egress** (setup phase, under the task's baseline policy):
   codex's CLI is installed with `apt` + `nvm` + `npm` inside the container;
2. **API egress** (agent phase): the model endpoint.

Widen the baseline per run — no task edits — with the TrialConfig
`environment.extra_allowed_hosts` override (the agent-phase-only
equivalent, `agent.extra_allowed_hosts`, is reachable from the CLI as
`--agent-arg extra_allowed_hosts='[...]'` but does **not** cover setup):

```python
import asyncio
from tide import Lab

INSTALL_HOSTS = [  # setup phase: apt / nvm / node / npm
    "deb.debian.org",
    "security.debian.org",
    "raw.githubusercontent.com",
    "github.com",
    "codeload.github.com",
    "nodejs.org",
    "registry.npmjs.org",
]
API_HOSTS = [  # agent phase: codex talking to OpenAI
    "chatgpt.com",
    "auth.openai.com",
    "api.openai.com",
]


async def main():
    lab = Lab("runs/codex")
    row = await lab.run(
        "tasks/autoresearch/circle-packing",
        agent={
            "name": "codex",
            "model_name": "openai/gpt-5.6-sol",  # any codex model slug
            "override_setup_timeout_sec": 1200,  # npm install can be slow
        },
        environment={"extra_allowed_hosts": INSTALL_HOSTS + API_HOSTS},
    )
    print(row.rewards)  # e.g. {'reward': 0.796...}; oracle baseline is 0.75


asyncio.run(main())
```

```bash
CODEX_FORCE_AUTH_JSON=1 python run_codex.py
```

The agent gets the task's `timeout_sec` as its budget (10 min here); hitting
the deadline is a normal ending — the verifier still grades the
best-so-far submission.

On tasks whose network is already open (e.g. the `frontier-cs` folders),
the plain CLI works: `tide run frontier-cs/frontier-cs-algorithm-1
--agent codex --model openai/gpt-5.6-sol`.

## Where the data lands

A `Lab` is a directory (`--lab`, default `runs/cli`):

```
runs/codex/
├── results.sqlite                  # one table for every run: episode rows + trace rows
└── trials/<task>__<id>/
    ├── agent/trajectory.json       # ATIF trajectory: every step + final_metrics
    │                               #   (tokens, cost_usd, duration)
    ├── agent/codex.txt             # the agent CLI's raw output
    ├── verifier/reward.json        # the final verdict
    ├── verifier/submissions.jsonl  # every judge-scored submission, with t
    └── result.json, config.json, trial.log
```

```bash
tide report --lab runs/codex       # summarize the store
```

Re-running the identical call returns the stored row instead of re-running
— the episode key is derived from (task, agent, tags). Vary a tag
(`--tag attempt=2`) to add attempts.

## Troubleshooting

- **`Cannot connect to the Docker daemon`** — start Docker Desktop first.
- **`network_mode='allowlist' is not supported by EnvironmentType.DOCKER`**
  — your Docker VM kernel lacks nftables FIB rules (Docker Desktop ≤ ~4.30).
  Upgrade Docker; until then, `--local` develops against the real judge, or
  copy the task and set `network_mode = "public"` for a smoke test whose
  scores are *not* isolation-backed (the optima are googleable, so treat
  them as pipeline checks, not results).
- **codex fails during setup with npm/apt errors** — the install hosts
  above aren't in the allowlist, or `override_setup_timeout_sec` is too
  small.
- **codex fails immediately with 401** — no credentials: set
  `OPENAI_API_KEY`, or `CODEX_FORCE_AUTH_JSON=1` with a valid
  `~/.codex/auth.json`.
