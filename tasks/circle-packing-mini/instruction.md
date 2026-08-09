# Circle packing (n=3)

Place **3 non-overlapping circles inside the unit square** to maximize the
**sum of their radii**. Circles must lie entirely inside the square and must
not overlap (tangency is allowed).

## Output format

Write your best solution to `/app/best/solution.json`:

```json
{"circles": [[x1, y1, r1], [x2, y2, r2], [x3, y3, r3]]}
```

## Scoring

- Your score is the sum of radii. Invalid solutions (overlap or out of bounds
  beyond tolerance 1e-9) score 0.
- A scorer is provided: `python /app/scorer.py /app/best/solution.json`
  prints the score. Call it as often as you like — but note the final grade
  is recomputed independently at higher precision, so violating constraints
  by tiny epsilons will score 0 there.

## Protocol (important)

- **Whenever you find a better solution, immediately write it to
  `/app/best/solution.json` atomically** (write to a temp file, then rename).
  You may be stopped at any moment; only what is in that file gets graded.
- Each time you improve, append one line to `/app/best/score_log.jsonl`:
  `{"t": <seconds since start>, "score": <your score>}`.

The known optimum for n=3 is ≈ 1.007626. Beat the greedy baseline (0.75)
and get as close to the optimum as you can within the budget.
