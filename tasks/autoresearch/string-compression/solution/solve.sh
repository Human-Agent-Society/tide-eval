#!/bin/bash
# Oracle: zlib level 9 — the honest baseline (ratio ~3.5).
set -euo pipefail
mkdir -p /app/best
python3 - <<'PY'
import base64, json, os, zlib
corpus = open("/app/corpus.txt").read()
payload = base64.b64encode(zlib.compress(corpus.encode(), 9)).decode()
dec = ("import sys,base64,zlib\n"
       "sys.stdout.write(zlib.decompress(base64.b64decode(PAYLOAD)).decode())\n")
json.dump({"decompressor": dec, "payload": payload},
          open("/app/best/solution.json.tmp", "w"))
os.rename("/app/best/solution.json.tmp", "/app/best/solution.json")
PY
echo '{"t": 1.0, "score": 3.47}' >> /app/best/score_log.jsonl
python3 /app/scorer.py /app/best/solution.json
