# Budget

Autoresearch has no finish line — only *how good, by when*. "When" is a
**budget**, and time is only one kind. A run is really bounded by whatever
resource is scarce:

| Dimension | `Budget` field | CLI flag | What it bounds |
|---|---|---|---|
| **Time** | `time_h` | `--budget <dur>` (`2h`, `30m`, `90s`; bare = hours) | wall-clock |
| **Evals** | `max_submissions` | `--max-evals <n>` | judge scorings (submissions) |
| **Tokens** | `max_tokens` | `--max-tokens <n>` (`500k`, `2m`) | LLM tokens |
| **Cost** | `max_cost_usd` | `--max-cost <usd>` | dollars spent |

Set the scarce one, leave the rest `None`. Comparing methods "at the same
budget" then means the same value on **whichever axis you're studying** — an
8h-vs-2h time curve, or reward-per-million-tokens across models.

```bash
tide run autoresearch/tsp-tour --agent claude-code --model anthropic/claude-opus-5 --budget 2h
tide run autoresearch/tsp-tour --agent codex        --max-tokens 500k
tide run autoresearch/tsp-tour --agent aider        --max-evals 50 --max-cost 3
```

```python
from tide import Lab, Budget

lab = Lab("runs/exp")
await lab.run(
    "tasks/autoresearch/tsp-tour",
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    budget=Budget(max_tokens=500_000),
)  # a bare number is hours: budget=2
```

## Set → deliver → record

Every dimension moves through the same three stages, so the numbers stay
comparable no matter how you integrate.

1. **Set** — one `Budget` on the run.
2. **Deliver** — each dimension is handed to the agent's container as a
   `TIDE_*` environment variable, next to the `$BUDGET_SEC` the local
   protocol already defines:

   | Field | env var seen in the container |
   |---|---|
   | `time_h` | `TIDE_BUDGET_SEC` |
   | `max_submissions` | `TIDE_MAX_SUBMISSIONS` |
   | `max_tokens` | `TIDE_MAX_TOKENS` |
   | `max_cost_usd` | `TIDE_MAX_COST_USD` |

   A harness or method reads these to pace itself. Ignoring them isn't
   cheating — it just spends more, and step 3 shows it.
3. **Record** — the budget is tagged on the episode (`budget`,
   `budget_max_tokens`, …) so runs group and pivot by it, and the **actual**
   spend comes back as `used_*` columns (see below). `tide report` and every
   `metrics` query read both.

## Enforcement is honest per dimension

tide does not pretend a black-box harness can be interrupted mid-thought.
What's hard vs. soft:

| Dimension | Enforcement |
|---|---|
| **Time** | **Hard.** `time_h` becomes the container timeout; the episode is killed at the deadline — a normal ending, and the verifier still grades the best-so-far snapshot. |
| **Evals** | **Hard at the task ceiling.** The judge enforces the task's own `judge_config.json` `max_submissions` and returns `429` past it. A *lower* per-run `--max-evals` is delivered as `TIDE_MAX_SUBMISSIONS` for the agent to honor (Harbor can't inject env into the judge sidecar), and the real count is always recorded. |
| **Tokens / Cost** | **Soft.** Signalled to the agent and recorded; use them to *budget* a method, and read `used_*` to see what actually happened. |

The design choice: **trust the measurement, not the promise.** A soft budget
you can verify after the fact beats a hard cap that silently changes what the
agent does.

## Measuring the spend — `used_*`

After every episode, the actual spend is recorded as columns on the episode
row:

| Column | Source |
|---|---|
| `used_n_submissions` | the judge's submission log (always available) |
| `used_n_input_tokens` / `used_n_output_tokens` / `used_n_total_tokens` | the harness's own usage accounting |
| `used_n_cache_tokens` | cache reads, when the harness reports them |
| `used_cost_usd` | the harness's cost accounting, when present |

### Where token counts come from (closed models included)

You rarely control the tokenizer of a closed model — but you don't have to.
Every mainstream harness already parses the **provider's own usage report**
out of its trajectory and Harbor surfaces it on the trial's `AgentContext`;
tide reads it straight off:

- **claude-code** — `usage` blocks in the trajectory (input / output / cache
  read + write), plus cost.
- **codex / qwen-code** — token counts from each turn's session log
  (`promptTokenCount` / `candidatesTokenCount` / cached).
- **aider, others** — whatever the adapter populates; missing fields are
  simply omitted rather than guessed.

These are the numbers the provider billed, so they're as exact as it gets for
a closed model — more accurate than re-tokenizing the prompt yourself (which
misses server-side system prompts, tool schemas, and cache accounting). When a
harness reports nothing (e.g. a no-LLM search method), the token columns are
absent and `used_n_submissions` still tells you the eval spend.

If you need a count a harness doesn't provide, count it at your own boundary
and POST it — but for supported harnesses the built-in numbers are the
recommended source.

## Querying by budget

Because budget and spend are both ordinary columns, the analyses are one call:

```python
from tide import metrics

df = lab.df("episode")

# What does more budget buy? (any axis — pass the budget column)
metrics.scaling(df, budget="budget_max_tokens", by=["model"])

# Reward per unit actually spent — the budget's flip side
metrics.efficiency(
    df, spend="used_n_total_tokens", per=1000, by=["model"]
)  # per 1k tokens
metrics.efficiency(df, spend="used_cost_usd", by=["model"])  # per dollar
```

Compare methods at the same budget tag, on the same tasks; `oracle` and `nop`
bracket the plausible range. See [metrics](metrics.md) for the full set.
