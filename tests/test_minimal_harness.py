"""The minimal harness's search loop, run end to end against the real
circle-packing judge on this machine — guards the example the README
points beginners at."""

import sys
from pathlib import Path

import pytest

from tide import Lab, LocalExecutor

ROOT = Path(__file__).parent.parent
TASK = str(ROOT / "tasks" / "autoresearch" / "first-party" / "circle-packing")
SEARCH = ROOT / "examples" / "minimal_harness_search.py"


async def test_random_search_speaks_the_judge_protocol(tmp_path):
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))
    row = await lab.run(
        TASK,
        {"command": f"{sys.executable} {SEARCH}", "override_timeout_sec": 3},
    )
    assert row.rewards["reward"] > 0  # random search finds a valid packing
    trace = lab.df("trace")
    assert len(trace) > 0  # every submission is in the log
    assert trace["score"].max() == pytest.approx(row.rewards["reward"])
