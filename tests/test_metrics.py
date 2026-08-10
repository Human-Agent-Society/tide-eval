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


def test_time_to_threshold():
    df = pd.DataFrame({"t": [1, 2, 3], "score": [0.2, 0.5, 0.9]})
    assert metrics.time_to(df, 0.5).iloc[0]["time_to"] == 2
    assert pd.isna(metrics.time_to(df, 0.95).iloc[0]["time_to"])


def test_time_to_grouped_includes_never_reached():
    df = pd.DataFrame(
        {
            "task": ["a", "a", "b", "b"],
            "t": [1, 2, 1, 2],
            "score": [0.3, 0.8, 0.1, 0.2],  # b never reaches 0.5
        }
    )
    out = metrics.time_to(df, 0.5, by=["task"]).set_index("task")
    assert out.loc["a", "time_to"] == 2
    assert pd.isna(out.loc["b", "time_to"])


def test_improvements_counts_and_rate():
    df = pd.DataFrame(
        {
            "t": [1, 2, 3, 4, 5],
            "score": [0.2, 0.1, 0.5, 0.5, 0.6],  # first, 0.5, 0.6 improve
        }
    )
    out = metrics.improvements(df)
    assert out.iloc[0]["evals"] == 5
    assert out.iloc[0]["improvements"] == 3
    assert out.iloc[0]["improvement_rate"] == pytest.approx(0.6)


def test_improvements_grouped():
    df = pd.DataFrame(
        {
            "task": ["a", "a", "b", "b", "b"],
            "t": [1, 2, 1, 2, 3],
            "score": [0.3, 0.4, 0.5, 0.2, 0.5],  # a: 2/2 · b: 1/3 (0.5 ties, not >)
        }
    )
    out = metrics.improvements(df, by=["task"]).set_index("task")
    assert out.loc["a", "improvement_rate"] == pytest.approx(1.0)
    assert out.loc["b", "improvements"] == 1
    assert out.loc["b", "improvement_rate"] == pytest.approx(1 / 3)


def test_rescale_linear_and_anchored():
    s = pd.Series([0.0, 5.0, 10.0, 15.0])
    lin = metrics.rescale_linear(s, lo=0, hi=10)
    assert lin.tolist() == [0.0, 50.0, 100.0, 100.0]  # clipped

    anch = metrics.rescale_anchored(s, baseline=0, top=10, super_anchor=20)
    assert anch.tolist() == [0.0, 50.0, 100.0, 150.0]  # beyond top stretches

    with pytest.raises(ValueError):
        metrics.rescale_linear(s, lo=1, hi=1)
