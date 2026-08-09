# TODO(task): title

TODO(task): the problem statement. State the reward formula explicitly.

## Output format

Write your best solution to `/app/best/solution.json`:

```json
{"TODO": "the exact schema"}
```

A scorer is provided: `python /app/scorer.py /app/best/solution.json`.
Call it freely; the final grade is recomputed independently.

## Protocol

- Whenever you improve, **atomically** rewrite `/app/best/solution.json`
  (temp file + rename); you may be stopped at any moment and only that
  file is graded.
- On each improvement, append `{"t": <seconds since start>, "score": <s>}`
  to `/app/best/score_log.jsonl`.
