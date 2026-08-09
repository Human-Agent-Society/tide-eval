# Function minimization

Minimize the Levi N.13 function over real (x, y):

```
f(x, y) = sin²(3πx) + (x−1)²(1 + sin²(3πy)) + (y−1)²(1 + sin²(2πy))
```

It is deceptive: gradient descent from most starts lands in one of many local
minima. Your **reward is 1 / (1 + f(x, y))** — the global optimum scores 1.0.

## Output format

Write your best point to `/app/best/solution.json`:

```json
{"x": 0.0, "y": 0.0}
```

A scorer is provided: `python /app/scorer.py /app/best/solution.json`.
Call it as often as you like; the final grade is recomputed independently.
Coordinates must be finite and within |v| ≤ 100.

## Protocol

- Whenever you find a better point, **atomically** rewrite
  `/app/best/solution.json` (write a temp file, then rename). You may be
  stopped at any moment; only that file is graded.
- On each improvement, append `{"t": <seconds since start>, "score": <s>}`
  to `/app/best/score_log.jsonl`.

Baseline for reference: the origin (0, 0) scores 1/3.
