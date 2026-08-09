#!/bin/bash
# Oracle: the identity tour — valid, reward exactly 1.0. Proves the pipeline.
set -euo pipefail
mkdir -p /app/best
python3 - <<'PY'
import json
n = len(json.load(open("/app/cities.json"))["cities"])
tmp = "/app/best/solution.json.tmp"
json.dump({"tour": list(range(n))}, open(tmp, "w"))
import os; os.rename(tmp, "/app/best/solution.json")
PY
echo '{"t": 1.0, "score": 1.0}' >> /app/best/score_log.jsonl
python3 /app/scorer.py /app/best/solution.json
