import pandas as pd
import pytest

from tide import metrics


def test_anytime_best_so_far_and_groups():
    df = pd.DataFrame({
        "task": ["a", "a", "a", "b", "b"],
        "t": [1, 2, 3, 1, 2],
        "score": [0.2, 0.1, 0.5, 0.4, 0.3],
    })
    out = metrics.anytime(df, by=["task"])
    a = out[out.task == "a"]["best_so_far"].tolist()
    b = out[out.task == "b"]["best_so_far"].tolist()
    assert a == [0.2, 0.2, 0.5]
    assert b == [0.4, 0.4]


def test_auc_left_riemann():
    curve = pd.DataFrame({"t": [0, 10], "best_so_far": [0.0, 1.0]})
    assert metrics.auc(curve) == 0.0  # holds 0.0 until t=10
    curve = pd.DataFrame({"t": [0, 5, 10], "best_so_far": [0.0, 1.0, 1.0]})
    assert metrics.auc(curve) == pytest.approx(0.5)


def test_scaling_groups_by_budget():
    df = pd.DataFrame({
        "budget": [2, 2, 4, 4],
        "reward": [0.1, 0.3, 0.5, 0.7],
    })
    out = metrics.scaling(df)
    assert out.set_index("budget")["reward"].to_dict() == {2: 0.2, 4: 0.6}


def test_matrix_forgetting_bwt():
    df = pd.DataFrame({
        "phase": [0, 0, 1, 1, 2, 2],
        "task": ["t0", "t1", "t0", "t1", "t0", "t1"],
        "reward": [0.9, 0.0, 0.8, 0.7, 0.5, 0.7],
    })
    m = metrics.matrix(df)
    f = metrics.forgetting(m)
    assert f["t0"] == pytest.approx(0.4)   # peaked 0.9, ended 0.5
    assert f["t1"] == pytest.approx(0.0)
    assert metrics.backward_transfer(m) == pytest.approx(-0.2)


def test_gain_and_missing_arm_is_loud():
    df = pd.DataFrame({
        "phase": [0, 0, 1, 1],
        "arm": ["stateful", "fresh", "stateful", "fresh"],
        "reward": [0.6, 0.5, 0.9, 0.5],
    })
    out = metrics.gain(df, by=["phase"]).set_index("phase")
    assert out.loc[1, "gain"] == pytest.approx(0.4)
    with pytest.raises(ValueError, match="arm='fresh'"):
        metrics.gain(df[df.arm == "stateful"], by=["phase"])


def test_internalization_ratio():
    df = pd.DataFrame({
        "task": ["t0", "t0"],
        "arm": ["in_context", "from_state"],
        "reward": [0.8, 0.6],
    })
    out = metrics.internalization(df, by=["task"])
    assert out["internalization"].iloc[0] == pytest.approx(0.75)


def test_rescale_linear_and_anchored():
    s = pd.Series([0.0, 5.0, 10.0, 15.0])
    lin = metrics.rescale_linear(s, lo=0, hi=10)
    assert lin.tolist() == [0.0, 50.0, 100.0, 100.0]  # clipped

    anch = metrics.rescale_anchored(s, baseline=0, top=10, super_anchor=20)
    assert anch.tolist() == [0.0, 50.0, 100.0, 150.0]  # beyond top stretches

    with pytest.raises(ValueError):
        metrics.rescale_linear(s, lo=1, hi=1)
