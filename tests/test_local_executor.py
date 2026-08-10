"""LocalExecutor: the real scorer and grader on the host, no containers."""

import sys
from pathlib import Path

from tide import Lab, LocalExecutor

TEMPLATE = str(Path(__file__).parent.parent / "tasks" / "_template")

WRITE_SOLUTION = """
import json, os, pathlib
app = pathlib.Path(os.environ["APP"])
(app / "best" / "solution.json").write_text(json.dumps({"x": 0.9}))
with (app / "best" / "score_log.jsonl").open("a") as f:
    f.write(json.dumps({"t": 1.0, "score": 0.9}) + "\\n")
"""


async def test_local_run_scores_for_real(tmp_path):
    script = tmp_path / "method.py"
    script.write_text(WRITE_SOLUTION)
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))

    row = await lab.run(
        TEMPLATE,
        {"command": f"{sys.executable} {script}", "override_timeout_sec": 30},
    )
    assert row.rewards == {"reward": 0.9}  # graded by the task's real grade.py
    assert row.uri.startswith("local://")  # provenance says: not isolation-backed
    assert lab.df("trace")["score"].tolist() == [0.9]


async def test_local_missing_artifact_scores_zero(tmp_path):
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))
    row = await lab.run(TEMPLATE, {"command": "true", "override_timeout_sec": 5})
    assert row.rewards == {"reward": 0.0}


async def test_local_rejects_non_template_tasks(tmp_path):
    (tmp_path / "not-a-task").mkdir()
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))
    row = await lab.run(str(tmp_path / "not-a-task"), {"command": "true"})
    assert row.rewards == {}
    assert "containers" in row.tags["error"]
