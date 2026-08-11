# Benchmark harness adapters

These adapters run three long-horizon systems against the same Tide task and
judge. They do not replace or wrap the scorer: every candidate still goes to
`$JUDGE_URL/submit`, the submission limit is enforced by the task, and Harbor's
verifier produces the final trusted reward.

Run an adapter from the repository root (Docker and `tide-eval[harbor]` are
required):

```bash
export OPENAI_API_KEY=...

python examples/run_harness.py openevolve --model gpt-5-mini --iterations 100
python examples/run_harness.py codex-goal --model gpt-5.6-terra --token-budget 40000
python examples/run_harness.py coral --model gpt-5.6-terra --agents 2
```

The example is wired to `tasks/autoresearch/circle-packing`, which makes the
three methods directly comparable in one Lab. Change `TASK` in
[`../run_harness.py`](../run_harness.py) to point at another task. Codex Goal
consumes the task instruction directly; replace OpenEvolve's candidate program
and CORAL's seed `solution.json` when adapting those harnesses to a new solution
format.

| Adapter | Integration | Pinned version |
|---|---|---|
| [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) | evolves `initial_program.py`; its evaluator executes the candidate and returns the Tide judge score | 0.3.2 |
| [Codex Goal mode](https://developers.openai.com/codex/app-server/) | uses `thread/goal/set`, the programmatic form of `/goal`, then waits for `complete` or `blocked` | Codex CLI 0.147.0 |
| [CORAL](https://github.com/Human-Agent-Society/CORAL) | launches a two-agent organization; `coral eval` calls a packaged `TaskGrader` that submits `solution.json` to Tide | 0.7.16 |

The adapters deliberately pin their tool versions so a benchmark record has a
meaningful harness version. Update the constants in
[`agents.py`](agents.py), the table above, and the protocol tests together.

## Credentials and network access

`run_harness.py` passes an environment-variable placeholder to Harbor, not the
API key value, so the key is resolved only when the agent starts. The Codex
adapters create their temporary `auth.json` inside the task container. Nothing
under that temporary home is declared as a task artifact.

The task must permit the model provider endpoint through its agent-phase network
policy. The judge itself remains the only scoring authority.
