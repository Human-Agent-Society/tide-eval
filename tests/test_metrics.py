import pandas as pd
import pytest

from tide import metrics


def test_anytime_best_so_far_and_groups():
    df = pd.DataFrame(
        {
            "task": ["a", "a", "a", "b", "b"],
            "t": [1, 2, 3, 1, 2],
            "score": [0.2, 0.1, 0.5, 0.4, 0.3],
        }
    )
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
    df = pd.DataFrame(
        {
            "budget": [2, 2, 4, 4],
            "reward": [0.1, 0.3, 0.5, 0.7],
        }
    )
    out = metrics.scaling(df)
    assert out.set_index("budget")["reward"].to_dict() == {2: 0.2, 4: 0.6}


def test_rescale_linear_and_anchored():
    s = pd.Series([0.0, 5.0, 10.0, 15.0])
    lin = metrics.rescale_linear(s, lo=0, hi=10)
    assert lin.tolist() == [0.0, 50.0, 100.0, 100.0]  # clipped

    anch = metrics.rescale_anchored(s, baseline=0, top=10, super_anchor=20)
    assert anch.tolist() == [0.0, 50.0, 100.0, 150.0]  # beyond top stretches

    with pytest.raises(ValueError):
        metrics.rescale_linear(s, lo=1, hi=1)
