"""Metrics: pure functions from DataFrame to DataFrame/Series.

Every function documents the **columns it expects** — this is the tag-hygiene
contract. The store never fixes a schema; a metric declares what it needs and
your script supplies those tags. Raw scores stay raw in the store; anything
normalization-shaped lives here and is applied at query time.

Conventions used throughout:

- ``score`` — the value column (``"reward"`` for episodes/probes, ``"score"``
  for trace rows; every function takes it as a parameter).
- Aggregation over repeats (k>1) is ``mean`` unless the metric says otherwise.
"""

from __future__ import annotations

import pandas as pd

# ------------------------------------------------------------------ curves


def anytime(
    df: pd.DataFrame, *, time: str = "t", score: str = "score",
    by: list[str] | None = None,
) -> pd.DataFrame:
    """Best-so-far curve over time — the autoresearch progress curve.

    Expects columns: *time*, *score*, plus any *by* group columns
    (typically task or version). Returns the input sorted by time with a
    ``best_so_far`` column (cumulative max within each group).
    """
    out = df.sort_values((by or []) + [time]).copy()
    grouped = out.groupby(by)[score] if by else out[score]
    out["best_so_far"] = grouped.cummax()
    return out


def auc(curve: pd.DataFrame, *, time: str = "t", value: str = "best_so_far") -> float:
    """Area under an anytime curve, normalized by the time span — the
    "anytime score". Expects the output of :func:`anytime` (one group)."""
    c = curve.sort_values(time)
    if len(c) < 2:
        return float(c[value].iloc[-1]) if len(c) else 0.0
    dt = c[time].diff().iloc[1:]
    heights = c[value].iloc[:-1].to_numpy()  # left Riemann: hold best until next point
    span = c[time].iloc[-1] - c[time].iloc[0]
    return float((heights * dt.to_numpy()).sum() / span) if span > 0 else 0.0


def scaling(
    df: pd.DataFrame, *, budget: str = "budget", score: str = "reward",
    by: list[str] | None = None,
) -> pd.DataFrame:
    """Score as a function of budget (EdgeBench's 2–12h curves).

    Expects columns: *budget*, *score*, plus optional *by* groups (model,
    category). Returns mean and count per (group, budget).
    """
    keys = (by or []) + [budget]
    return (
        df.groupby(keys)[score].agg(["mean", "count"]).reset_index()
        .rename(columns={"mean": score})
    )


# ------------------------------------------------------- stream / CL views


def matrix(
    df: pd.DataFrame, *, row: str = "phase", col: str = "task",
    score: str = "reward",
) -> pd.DataFrame:
    """The version × task accuracy matrix. Expects columns *row*, *col*,
    *score*. Cell = mean over repeats. Rows/cols sorted."""
    return df.pivot_table(index=row, columns=col, values=score, aggfunc="mean").sort_index()


def forgetting(m: pd.DataFrame) -> pd.Series:
    """Per-task forgetting from an accuracy matrix (rows = phases in order):
    ``max over earlier phases − final phase``. Positive = forgot."""
    return m.cummax().iloc[-1] - m.iloc[-1]


def backward_transfer(m: pd.DataFrame) -> float:
    """Average change on old tasks after learning new ones (negative of mean
    forgetting) — the standard BWT summary."""
    return float(-forgetting(m).mean())


def gain(
    df: pd.DataFrame, *, arm: str = "arm", score: str = "reward",
    by: list[str] | None = None,
    treatment: str = "stateful", control: str = "fresh",
) -> pd.DataFrame:
    """CL-Bench-style gain: how much of the score is *learning* rather than
    raw capability.

    Expects an *arm* column with two values (default ``stateful`` /
    ``fresh``): the same episodes run with and without carried state. Returns
    per-group means of both arms and their difference (``gain``).
    """
    keys = by or []
    wide = df.pivot_table(index=keys or None, columns=arm, values=score, aggfunc="mean")
    for needed in (treatment, control):
        if needed not in wide.columns:
            raise ValueError(
                f"gain() needs arm={needed!r} rows; found arms {list(wide.columns)}"
            )
    wide = wide[[treatment, control]].copy()
    wide["gain"] = wide[treatment] - wide[control]
    return wide.reset_index() if keys else wide


def internalization(
    df: pd.DataFrame, *, arm: str = "arm", score: str = "reward",
    by: list[str] | None = None,
) -> pd.DataFrame:
    """From-state score as a fraction of in-context score: how much survived
    being moved from the prompt into the learner's state.

    Expects an *arm* column with values ``in_context`` and ``from_state``.
    """
    out = gain(
        df, arm=arm, score=score, by=by,
        treatment="from_state", control="in_context",
    ).drop(columns=["gain"])
    out["internalization"] = out["from_state"] / out["in_context"]
    return out


# -------------------------------------------------------------- normalizers


def rescale_linear(s: pd.Series, *, lo: float, hi: float) -> pd.Series:
    """Map raw scores to 0–100 linearly, clipped. ``lo`` → 0, ``hi`` → 100."""
    if hi == lo:
        raise ValueError("rescale_linear needs hi != lo")
    return ((s - lo) / (hi - lo) * 100).clip(0, 100)


def rescale_anchored(
    s: pd.Series, *, baseline: float, top: float, super_anchor: float | None = None,
) -> pd.Series:
    """EdgeBench-style piecewise rescale: baseline → 0, top → 100, and scores
    beyond ``super_anchor`` (if given) stretch linearly above 100 — so beating
    the best known result is visible rather than clipped."""
    scaled = rescale_linear(s, lo=baseline, hi=top)
    if super_anchor is not None:
        over = s > top
        scaled[over] = 100 + (s[over] - top) / (super_anchor - top) * 100
    return scaled
