import pytest

from tide import StateDir, StaticWeightPlane


@pytest.fixture()
def state(tmp_path):
    return StateDir(tmp_path / "state")


def test_snapshot_materialize_roundtrip(state, tmp_path):
    (state.path / "memory.md").write_text("v1: markets are mean-reverting\n")
    ref1 = state.snapshot("phase 1")

    (state.path / "memory.md").write_text("v2: except when they trend\n")
    ref2 = state.snapshot("phase 2")
    assert ref1 != ref2

    old = state.materialize(ref1, tmp_path / "old")
    assert (old / "memory.md").read_text().startswith("v1")
    # live dir untouched by materializing history
    assert (state.path / "memory.md").read_text().startswith("v2")


def test_snapshot_idempotent_when_unchanged(state):
    (state.path / "a.txt").write_text("x")
    ref1 = state.snapshot()
    ref2 = state.snapshot()
    assert ref1 == ref2


def test_refs_oldest_first_and_diff(state):
    (state.path / "a.txt").write_text("1")
    r1 = state.snapshot()
    (state.path / "a.txt").write_text("2")
    r2 = state.snapshot()
    assert state.refs() == [r1, r2]
    assert "-1" in state.diff(r1, r2) and "+2" in state.diff(r1, r2)


def test_static_weight_plane_contract():
    plane = StaticWeightPlane("http://localhost:8000/v1")
    ref = plane.snapshot()
    assert plane.serve(ref) == "http://localhost:8000/v1"
    with pytest.raises(KeyError):
        plane.serve("v999")
