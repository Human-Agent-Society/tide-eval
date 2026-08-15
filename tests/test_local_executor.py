"""LocalExecutor: the task's real judge as a local process, no containers."""

import sys
from pathlib import Path

from tide import Lab, LocalExecutor

TEMPLATE = str(Path(__file__).parent.parent / "tasks" / "_template")

SUBMIT_TWICE = """
import json, os, urllib.request

def submit(payload):
    req = urllib.request.Request(
        os.environ["JUDGE_URL"] + "/submit", data=json.dumps(payload).encode()
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

print(submit({"x": 0.4}))
print(submit({"x": 0.9}))
"""


async def test_local_run_goes_through_the_real_judge(tmp_path):
    script = tmp_path / "method.py"
    script.write_text(SUBMIT_TWICE)
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))

    row = await lab.run(
        TEMPLATE,
        {"command": f"{sys.executable} {script}", "override_timeout_sec": 30},
    )
    assert row.rewards == {"reward": 0.9}  # best submission, judged for real
    assert row.uri.startswith("local://")  # provenance: not isolation-backed
    assert lab.df("trace")["score"].tolist() == [0.4, 0.9]  # the submission log


async def test_local_no_submissions_scores_zero(tmp_path):
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))
    row = await lab.run(TEMPLATE, {"command": "true", "override_timeout_sec": 10})
    assert row.rewards == {"reward": 0.0}


async def test_local_delivers_stream_state_dir(tmp_path):
    """Under --local the carried state is the host path itself — no mount."""
    state = tmp_path / "state"
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))
    await lab.run(
        TEMPLATE,
        {
            "command": 'echo remembered > "$TIDE_STATE_DIR/note"',
            "override_timeout_sec": 10,
        },
        state_dir=str(state),
    )
    assert (state / "note").read_text().strip() == "remembered"


async def test_local_rejects_non_template_tasks(tmp_path):
    (tmp_path / "not-a-task").mkdir()
    lab = Lab(tmp_path / "lab", executor=LocalExecutor(root=tmp_path))
    row = await lab.run(str(tmp_path / "not-a-task"), {"command": "true"})
    assert row.rewards == {}
    assert "containers" in row.tags["error"]
