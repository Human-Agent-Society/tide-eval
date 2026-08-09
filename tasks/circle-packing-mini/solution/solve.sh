#!/bin/bash
# Oracle solution: a valid greedy packing (three r=0.25 circles, sum 0.75).
# Exists so `oracle` runs prove the pipeline: env builds, artifacts flow,
# the separate verifier grades > 0. Beating this is the agent's job.
set -euo pipefail

mkdir -p /app/best
cat > /app/best/solution.json.tmp <<'EOF'
{"circles": [[0.25, 0.25, 0.25], [0.75, 0.25, 0.25], [0.25, 0.75, 0.25]]}
EOF
mv /app/best/solution.json.tmp /app/best/solution.json
echo '{"t": 1.0, "score": 0.75}' >> /app/best/score_log.jsonl
python3 /app/scorer.py /app/best/solution.json
