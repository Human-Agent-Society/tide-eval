#!/bin/bash
# Oracle baseline: a valid, deliberately beatable solution. Proves the
# pipeline (env builds, artifacts flow, verifier grades > 0).
# TODO(task): write your baseline solution atomically.
set -euo pipefail
mkdir -p /app/best
printf '{"x": 0.5}' > /app/best/solution.json.tmp
mv /app/best/solution.json.tmp /app/best/solution.json
echo '{"t": 1.0, "score": 0.5}' >> /app/best/score_log.jsonl
python3 /app/scorer.py /app/best/solution.json
