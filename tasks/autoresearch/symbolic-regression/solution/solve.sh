#!/bin/bash
# Oracle: a plain quadratic fit — decent on train, imperfect held-out.
# Deliberately NOT the true formula; proves the pipeline with a mid score.
set -euo pipefail
printf '{"expr": "0.5 * x**2"}' > /tmp/solution.json
python3 - <<'PY'
import json, os, urllib.request
req = urllib.request.Request(
    os.environ["JUDGE_URL"] + "/submit", data=open("/tmp/solution.json", "rb").read()
)
print(json.loads(urllib.request.urlopen(req, timeout=60).read()))
PY
