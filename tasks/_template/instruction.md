# Maximize x   <!-- TODO(task): replace the problem; keep the protocol -->

Find the largest `x` in `[0, 1]`. Your score is `x` itself.

(This placeholder problem is trivial on purpose — the template ships as a
complete working task so you can copy it, see the suite pass, then replace
the problem while keeping the protocol below.)

## Output format

Write your best solution to `/app/best/solution.json`:

```json
{"x": 0.5}
```

A scorer is provided: `python /app/scorer.py /app/best/solution.json`.
Call it freely; the final grade is recomputed independently.

## Protocol

- Whenever you improve, **atomically** rewrite `/app/best/solution.json`
  (temp file + rename); you may be stopped at any moment and only that
  file is graded.
- On each improvement, append `{"t": <seconds since start>, "score": <s>}`
  to `/app/best/score_log.jsonl`.
