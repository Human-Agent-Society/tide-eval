"""The in-container half of the minimal harness: random search, pure stdlib.

This is what an autoresearch "method" looks like from inside the task
container. It speaks the task contract and nothing else:

- call the task's public scorer (``/app/scorer.py``) as its feedback signal;
- keep the best solution atomically written to ``/app/best/solution.json``;
- append one line per improvement to ``/app/best/score_log.jsonl``.

No LLM, no API keys — it samples random candidates until the budget ends.
``APP`` and ``BUDGET_SEC`` are env-overridable so the same script runs
against a local copy of the scorer in tests.
"""

import json
import os
import random
import sys
import time

APP = os.environ.get("APP", "/app")
BUDGET_SEC = float(os.environ.get("BUDGET_SEC", "30"))

sys.path.insert(0, APP)
from scorer import score  # noqa: E402 — the task's public scorer

best_path = os.path.join(APP, "best", "solution.json")
log_path = os.path.join(APP, "best", "score_log.jsonl")
cand_path = os.path.join(APP, "best", ".candidate.json")

t0 = time.monotonic()
best = 0.0
while time.monotonic() - t0 < BUDGET_SEC:
    circles = [
        [random.random(), random.random(), random.uniform(0.02, 0.35)] for _ in range(3)
    ]
    with open(cand_path, "w") as f:
        json.dump({"circles": circles}, f)
    s = score(cand_path)
    if s > best:
        best = s
        os.replace(cand_path, best_path)  # atomic: same directory
        with open(log_path, "a") as f:
            f.write(
                json.dumps({"t": round(time.monotonic() - t0, 3), "score": s}) + "\n"
            )

print(f"random search done: best={best:.4f}")
