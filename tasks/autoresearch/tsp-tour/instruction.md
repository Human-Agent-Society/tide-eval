# Traveling salesman: shorten the tour

`/app/cities.json` holds 40 fixed cities in the unit square. Find a short
**closed tour** visiting every city exactly once.

**Reward = (identity-tour length) / (your tour length).** Visiting cities in
file order scores exactly 1.0; every improvement pushes the reward above 1.0.
Good heuristics (nearest-neighbor + 2-opt and beyond) reach ~1.8–2.0.

## Output format

Write your best tour to `/app/best/solution.json`:

```json
{"tour": [0, 17, 5, ...]}
```

A permutation of 0..39. A scorer is provided:
`python /app/scorer.py /app/best/solution.json` — call it freely; the final
grade is recomputed independently (invalid permutations score 0).

## Protocol

- Whenever you find a shorter tour, **atomically** rewrite
  `/app/best/solution.json` (temp file + rename); only that file is graded.
- On each improvement, append `{"t": <seconds since start>, "score": <s>}`
  to `/app/best/score_log.jsonl`.
