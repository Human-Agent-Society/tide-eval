#!/bin/bash
# Oracle baseline: a valid, deliberately beatable solution. Proves the
# pipeline (env builds, artifacts flow, verifier grades > 0).
set -euo pipefail
mkdir -p /app/best
# TODO(task): write the baseline solution atomically
printf '{"TODO": "solution"}' > /app/best/solution.json.tmp
mv /app/best/solution.json.tmp /app/best/solution.json
echo '{"t": 1.0, "score": 0.0}' >> /app/best/score_log.jsonl
python3 /app/scorer.py /app/best/solution.json
