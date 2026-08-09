#!/bin/bash
# Oracle: the origin — a deliberately mediocre valid point (reward exactly
# 1/3). Proves the pipeline; beating it is the agent's job.
set -euo pipefail
mkdir -p /app/best
printf '{"x": 0.0, "y": 0.0}' > /app/best/solution.json.tmp
mv /app/best/solution.json.tmp /app/best/solution.json
echo '{"t": 1.0, "score": 0.3333333333}' >> /app/best/score_log.jsonl
python3 /app/scorer.py /app/best/solution.json
