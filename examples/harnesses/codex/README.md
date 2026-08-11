# Tide Codex Goal harness

This package drives Codex Goal mode over the app-server JSON-RPC protocol. It
sets the same persisted goal state as interactive `/goal`, starts the first
turn, and keeps the connection open while Codex automatically continues toward
the objective.

The package expects the `codex` CLI to be installed and authenticated. From an
activated environment:

```bash
pip install ./examples/harnesses/codex
tide-codex-goal objective.txt --model gpt-5.6-terra --token-budget 40000
```

Pass `--usage-file usage.jsonl` to persist the final input, cached-input, and
output token totals reported by `thread/tokenUsage/updated`.

The Harbor adapter installs the pinned Codex CLI and this package inside the
task container automatically. `CODEX_APP_SERVER_COMMAND` may override the
default `codex app-server --stdio` command for protocol tests.
