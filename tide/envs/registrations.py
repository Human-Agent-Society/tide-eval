"""Built-in env registrations — the catalog, as Gym-style ids.

Ids are stable, versioned handles: a breaking change to a task's data or
scoring bumps ``-vN`` and keeps old results reproducible.
"""

from __future__ import annotations

from typing import Any

from tide.envs.registry import register
from tide.paths import resolve_bench

_TASK_OBS = "dict: `instruction` (markdown) + `files` (the task's data files)"
_TASK_ACT = "a candidate solution object (the task's solution.json schema)"


class _ResolvedTaskEnv:
    """Late-binding TaskEnv: resolves the tasks catalog at construction.

    ``step_scorer_name`` names a callable in :mod:`tide.envs.task_env`
    (registry kwargs stay plain data so specs remain serializable).
    """

    def __new__(cls, relative: str, step_scorer_name: str | None = None, **kwargs: Any):
        from tide.envs import task_env

        if step_scorer_name is not None:
            kwargs["step_scorer"] = getattr(task_env, step_scorer_name)
        return task_env.TaskEnv(resolve_bench(relative), **kwargs)


class _ResolvedStream:
    def __new__(cls, kind: str, relative: str):
        from tide.envs import stream_env

        return getattr(stream_env, kind)(resolve_bench(relative))


def _task(
    name: str,
    relative: str,
    description: str,
    reward_doc: str,
    extra: dict | None = None,
) -> None:
    register(
        f"tide/{name}-v0",
        entry_point="tide.envs.registrations:_ResolvedTaskEnv",
        kwargs={"relative": relative, **(extra or {})},
        description=description,
        observation_doc=_TASK_OBS,
        action_doc=_TASK_ACT,
        reward_doc=reward_doc,
    )


_task(
    "CirclePacking",
    "autoresearch/circle-packing",
    "Pack 3 circles in the unit square, maximize the sum of radii.",
    "sum of radii; 0 for any constraint violation (exact arithmetic). Oracle 0.75, optimum ≈1.0076.",
)
_task(
    "FunctionMinimization",
    "autoresearch/function-minimization",
    "Minimize the deceptive Levi N.13 function.",
    "1/(1+f(x,y)); global optimum scores 1.0, the origin scores 1/3.",
)
_task(
    "TspTour",
    "autoresearch/tsp-tour",
    "Find a short closed tour over 40 fixed cities.",
    "identity-tour length / yours; 1.0 = file order, ~2.0 = strong heuristics; invalid permutation = 0.",
)
_task(
    "BinPacking",
    "autoresearch/bin-packing",
    "Pack 60 items into as few capacity-100 bins as possible.",
    "first-fit bins / yours; 1.0 = first-fit; any constraint violation = 0.",
)
_task(
    "SymbolicRegression",
    "autoresearch/symbolic-regression",
    "Recover a hidden formula from noiseless samples.",
    "steps: 1/(1+RMSE) on TRAIN points; final(): on HELD-OUT points — the anti-overfitting wall.",
    extra={"step_scorer_name": "symbolic_regression_train_scorer"},
)
_task(
    "StringCompression",
    "autoresearch/string-compression",
    "Ship a decompressor + payload that reproduces the corpus byte-exactly.",
    "corpus bytes / compressed bytes (zlib ≈3.47); failed round trip = 0. Decompressor runs sandboxed, ≤15s.",
)

register(
    "tide/OceanFacts-v0",
    entry_point="tide.envs.registrations:_ResolvedStream",
    kwargs={"kind": "ocean_facts_env", "relative": "streams/ocean-facts"},
    description="8-document ingest-then-probe stream; every phase re-asks all questions seen so far.",
    observation_doc="dict: `phase`, `ingest` (the document to learn), `questions` (chat messages, cumulative)",
    action_doc="list[str]: one answer per question, in order",
    reward_doc="fraction of answers containing the expected fact (deterministic keyword judge)",
)
register(
    "tide/HiddenRules-v0",
    entry_point="tide.envs.registrations:_ResolvedStream",
    kwargs={"kind": "hidden_rules_env", "relative": "streams/hidden-rules"},
    description="Infer a hidden linear rule across 6 phases; accumulating observations should widen the gain.",
    observation_doc="dict: `phase`, `ingest` (this phase's observed rounds), `questions` (the query block)",
    action_doc="list[str]: one response containing 'Round n: WIN/LOSS' lines",
    reward_doc="fraction of query rounds labeled correctly (deterministic exact-line judge)",
)
