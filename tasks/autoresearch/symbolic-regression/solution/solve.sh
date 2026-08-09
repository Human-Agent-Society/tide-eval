#!/bin/bash
# Oracle: a plain quadratic fit — decent on train, imperfect held-out.
# Deliberately NOT the true formula; proves the pipeline with a mid score.
set -euo pipefail
mkdir -p /app/best
printf '{"expr": "0.5 * x**2"}' > /app/best/solution.json.tmp
mv /app/best/solution.json.tmp /app/best/solution.json
echo '{"t": 1.0, "score": 0.6}' >> /app/best/score_log.jsonl
python3 /app/scorer.py /app/best/solution.json
