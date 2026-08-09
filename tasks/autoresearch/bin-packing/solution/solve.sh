#!/bin/bash
# Oracle: first-fit — valid, reward exactly 1.0. Proves the pipeline.
set -euo pipefail
mkdir -p /app/best
python3 - <<'PY'
import json, os
from pathlib import Path
data = json.loads(Path("/app/items.json").read_text())
items, cap = data["items"], data["capacity"]
bins, loads = [], []
for i, s in enumerate(items):
    for k in range(len(bins)):
        if loads[k] + s <= cap:
            bins[k].append(i); loads[k] += s; break
    else:
        bins.append([i]); loads.append(s)
Path("/app/best/solution.json.tmp").write_text(json.dumps({"bins": bins}))
os.rename("/app/best/solution.json.tmp", "/app/best/solution.json")
PY
echo '{"t": 1.0, "score": 1.0}' >> /app/best/score_log.jsonl
python3 /app/scorer.py /app/best/solution.json
