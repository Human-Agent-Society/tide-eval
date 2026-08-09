# Symbolic regression

`/app/train.json` holds 40 noiseless samples (x, y) of an unknown function
on roughly x ∈ [−3, 3]. Recover the formula.

## Output format

Write your best expression to `/app/best/solution.json`:

```json
{"expr": "0.5 * x**2 + sin(x)"}
```

Allowed: numbers, `x`, `+ - * / **`, unary minus, and
`sin cos tan exp log sqrt abs`. Anything else scores 0. Max 2000 chars.

## Scoring — read this carefully

`python /app/scorer.py /app/best/solution.json` reports 1/(1+RMSE) on the
**training** points. The trusted grade is 1/(1+RMSE) on **held-out points
you never see, on a slightly wider range**. An expression that memorizes the
training set (e.g. a huge interpolating polynomial) will score near 1.0
locally and collapse on the real grade. Only the true structure generalizes
— the exact formula scores 1.0.

## Protocol

- Whenever you find a better expression, **atomically** rewrite
  `/app/best/solution.json` (temp file + rename); only that file is graded.
- On each improvement, append `{"t": <seconds since start>, "score": <s>}`
  to `/app/best/score_log.jsonl`.
