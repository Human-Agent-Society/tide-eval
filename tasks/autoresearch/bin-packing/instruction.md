# Bin packing

`/app/items.json` holds 60 item sizes and a bin capacity of 100. Pack every
item into as few bins as possible.

**Reward = (first-fit bin count) / (your bin count).** The classic first-fit
heuristic scores exactly 1.0; every bin you save pushes the reward above 1.0.
(First-fit-decreasing and smarter searches do save bins here.)

## Output format

Write your best packing to `/app/best/solution.json`:

```json
{"bins": [[0, 7, 12], [1, 3], ...]}
```

Item indices, each appearing exactly once; every bin's sizes must sum to
≤ 100. A scorer is provided: `python /app/scorer.py /app/best/solution.json`.
The final grade is recomputed independently — invalid packings score 0.

## Protocol

- Whenever you save a bin, **atomically** rewrite
  `/app/best/solution.json` (temp file + rename); only that file is graded.
- On each improvement, append `{"t": <seconds since start>, "score": <s>}`
  to `/app/best/score_log.jsonl`.
