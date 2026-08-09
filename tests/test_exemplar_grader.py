"""The anti-hack wall, as a permanent test.

Loads the exemplar task's trusted grader and proves: the oracle scores its
known value, constraint cheats (overlap, out-of-bounds, float-epsilon) score
zero, and forged score logs can't influence it (it never reads them).
"""

import importlib.util
import json
from pathlib import Path

import pytest

GRADE_PY = (
    Path(__file__).parent.parent
    / "examples" / "tasks" / "circle-packing-mini" / "tests" / "grade.py"
)


@pytest.fixture()
def grade(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("grade", GRADE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def run(circles=None, *, artifact=None):
        if circles is not None:
            artifact = tmp_path / "solution.json"
            artifact.write_text(json.dumps({"circles": circles}))
        monkeypatch.setattr(
            module, "find_artifact",
            lambda name, _a=artifact: _a if name == "solution.json" else None,
        )
        return module.grade()

    return run


def test_oracle_scores_its_known_value(grade):
    oracle = [[0.25, 0.25, 0.25], [0.75, 0.25, 0.25], [0.25, 0.75, 0.25]]
    assert grade(oracle)["reward"] == pytest.approx(0.75)


def test_overlap_scores_zero(grade):
    overlapping = [[0.4, 0.5, 0.2], [0.75, 0.5, 0.2], [0.5, 0.1, 0.05]]
    result = grade(overlapping)
    assert result["reward"] == 0.0
    assert "overlap" in result["reason"]


def test_epsilon_cheat_scores_zero(grade):
    # 5e-9 overlap: beyond the documented 1e-9 tolerance. Buying radius with
    # float epsilons must not pay.
    eps = [[0.3, 0.5, 0.2], [0.7, 0.5, 0.2 + 5e-9], [0.5, 0.1, 0.05]]
    assert grade(eps)["reward"] == 0.0


def test_tangency_within_tolerance_accepted(grade):
    tangent = [[0.3, 0.5, 0.2], [0.7, 0.5, 0.2], [0.5, 0.1, 0.05]]
    assert grade(tangent)["reward"] == pytest.approx(0.45)


def test_out_of_bounds_scores_zero(grade):
    oob = [[0.5, 0.5, 0.51], [0.1, 0.1, 0.05], [0.9, 0.9, 0.02]]
    result = grade(oob)
    assert result["reward"] == 0.0
    assert "outside" in result["reason"]


def test_missing_or_malformed_artifact_scores_zero(grade):
    assert grade(artifact=None)["reward"] == 0.0


def test_forged_claims_are_ignored(grade, tmp_path):
    # The grader's only input is the solution artifact: a forged score log or
    # an inflated claimed score simply has no channel into the result.
    artifact = tmp_path / "solution.json"
    artifact.write_text(json.dumps({
        "circles": [[0.25, 0.25, 0.25], [0.75, 0.25, 0.25], [0.25, 0.75, 0.25]],
        "claimed_score": 999.0,
    }))
    assert grade(artifact=artifact)["reward"] == pytest.approx(0.75)
