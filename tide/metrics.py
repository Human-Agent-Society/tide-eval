"""Metrics: pure functions from DataFrame to DataFrame/Series.

Every function documents the **columns it expects** — this is the tag-hygiene
contract. The store never fixes a schema; a metric declares what it needs and
your script supplies those tags. Raw scores stay raw in the store; anything
normalization-shaped lives here and is applied at query time.

Conventions used throughout:

- ``score`` — the value column (``"reward"`` for episodes, ``"score"``
  for trace rows; every function takes it as a parameter).
- Aggregation over repeats (k>1) is ``mean`` unless the metric says otherwise.
"""

from __future__ import annotations

import pandas as pd

# ------------------------------------------------------------------ curves


def anytime(
    df: pd.DataFrame,
    *,
    time: str = "t",
    score: str = "score",
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
    df: pd.DataFrame,
    *,
    budget: str = "budget",
    score: str = "reward",
    by: list[str] | None = None,
) -> pd.DataFrame:
    """Score as a function of budget (EdgeBench's 2–12h curves).

    Expects columns: *budget*, *score*, plus optional *by* groups (model,
    category). Returns mean and count per (group, budget).
    """
    keys = (by or []) + [budget]
    return (
        df.groupby(keys)[score]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": score})
    )


def time_to(
    df: pd.DataFrame,
    threshold: float,
    *,
    time: str = "t",
    score: str = "score",
    by: list[str] | None = None,
) -> pd.DataFrame:
    """When did the score first reach *threshold*?

    Expects columns *time*, *score* (+ *by* groups). Returns one row per
    group with ``time_to`` — the earliest *time* whose score meets the
    threshold, or NaN if the group never reached it.
    """
    hits = df[df[score] >= threshold]
    if not by:
        value = hits[time].min() if len(hits) else float("nan")
        return pd.DataFrame([{"time_to": value}])
    reached = hits.groupby(by)[time].min().rename("time_to").reset_index()
    every_group = df[by].drop_duplicates()
    return every_group.merge(reached, on=by, how="left")


def improvements(
    df: pd.DataFrame,
    *,
    time: str = "t",
    score: str = "score",
    by: list[str] | None = None,
) -> pd.DataFrame:
    """How often self-evaluation actually raised the score.

    Expects columns: *time*, *score* (+ *by* groups). Per group:
    ``evals`` (total points), ``improvements`` (points strictly above the
    best so far; the first point counts), and their ratio
    ``improvement_rate``.

    The ledger records every submission, so the rate is a real property of
    the method: how often spending a submission actually helped.
    """
    out = df.sort_values((by or []) + [time])
    if by:
        cummax = out.groupby(by)[score].cummax()
        prev_best = cummax.groupby([out[k] for k in by]).shift()
    else:
        prev_best = out[score].cummax().shift()
    out = out.assign(_improved=prev_best.isna() | (out[score] > prev_best))
    if not by:
        n = len(out)
        k = int(out["_improved"].sum())
        return pd.DataFrame(
            [{"evals": n, "improvements": k, "improvement_rate": k / n if n else 0.0}]
        )
    agg = out.groupby(by).agg(evals=(score, "size"), improvements=("_improved", "sum"))
    agg["improvement_rate"] = agg["improvements"] / agg["evals"]
    return agg.reset_index()


# -------------------------------------------------------------- normalizers


def rescale_linear(s: pd.Series, *, lo: float, hi: float) -> pd.Series:
    """Map raw scores to 0–100 linearly, clipped. ``lo`` → 0, ``hi`` → 100."""
    if hi == lo:
        raise ValueError("rescale_linear needs hi != lo")
    return ((s - lo) / (hi - lo) * 100).clip(0, 100)


def rescale_anchored(
    s: pd.Series,
    *,
    baseline: float,
    top: float,
    super_anchor: float | None = None,
) -> pd.Series:
    """EdgeBench-style piecewise rescale: baseline → 0, top → 100, and scores
    beyond ``super_anchor`` (if given) stretch linearly above 100 — so beating
    the best known result is visible rather than clipped."""
    scaled = rescale_linear(s, lo=baseline, hi=top)
    if super_anchor is not None:
        over = s > top
        scaled[over] = 100 + (s[over] - top) / (super_anchor - top) * 100
    return scaled
