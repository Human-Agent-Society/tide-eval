"""The minimal harness's in-container half, run offline against the real
task scorer — guards the example the README points beginners at."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SEARCH = ROOT / "examples" / "minimal_harness_search.py"
SCORER = (
    ROOT / "tasks" / "autoresearch" / "circle-packing" / "environment" / "scorer.py"
)


def test_search_speaks_the_task_contract(tmp_path):
    app = tmp_path / "app"
    (app / "best").mkdir(parents=True)
    shutil.copy(SCORER, app / "scorer.py")

    result = subprocess.run(
        [sys.executable, str(SEARCH)],
        env={**os.environ, "APP": str(app), "BUDGET_SEC": "1.5"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    # The gradeable artifact exists and actually scores > 0.
    solution = json.loads((app / "best" / "solution.json").read_text())
    assert len(solution["circles"]) == 3

    sys.path.insert(0, str(app))
    try:
        from scorer import score

        assert score(str(app / "best" / "solution.json")) > 0
    finally:
        sys.path.remove(str(app))
        sys.modules.pop("scorer", None)

    # The score log is valid, monotone in t, and its last line is the best.
    lines = [
        json.loads(line)
        for line in (app / "best" / "score_log.jsonl").read_text().splitlines()
    ]
    assert lines and all("t" in p and "score" in p for p in lines)
    scores = [p["score"] for p in lines]
    assert scores == sorted(scores)  # only improvements are logged
