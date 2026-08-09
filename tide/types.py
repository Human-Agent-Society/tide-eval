"""Core data types shared across tide.

The vocabulary is deliberately tiny:

- An :class:`EpisodeSpec` says what to run (a Harbor task + an agent).
- An :class:`EpisodeResult` is what an executor hands back.
- A :class:`TracePoint` is one untrusted intermediate score emitted *during*
  an episode (an agent self-evaluation, a trade, a checkpoint probe).
- A :class:`Row` is what actually lands in the results store.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

Tags = dict[str, Any]
Rewards = dict[str, float | int]


@dataclass(frozen=True)
class EpisodeSpec:
    """What to run: a Harbor task under a given agent configuration.

    ``task`` is a Harbor task directory path or a registry id
    (e.g. ``"terminal-bench/hello-world"``). ``agent`` uses Harbor's own
    ``AgentConfig`` field names verbatim (``name``, ``model_name``,
    ``import_path``, ...) — tide adds no translation layer.
    ``overrides`` are passed through to Harbor's ``TrialConfig`` for anything
    else (verifier/environment settings, timeout multipliers, ...).
    """

    task: str
    agent: dict[str, Any]
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TracePoint:
    """One untrusted intermediate score from inside an episode.

    ``t`` is seconds since the episode started (or any monotonic offset the
    task convention defines). ``data`` carries anything else the score log
    recorded (snapshot path, trade id, ...).
    """

    t: float
    score: float
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EpisodeResult:
    """What an executor returns for one episode.

    ``rewards`` is the trusted verdict (from Harbor's verifier, or a fake in
    tests). ``trace`` is the untrusted score trajectory recovered from the
    episode's artifacts. ``uri`` points at the provenance (the Harbor trial
    directory) so every stored number stays auditable.
    """

    rewards: Rewards
    uri: str | None = None
    trace: tuple[TracePoint, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class Row:
    """One record in the results store. ``kind`` is one of:

    - ``episode`` — a trusted, verifier-backed score (one per episode)
    - ``trace``   — an untrusted intermediate score (many per episode)
    - ``probe``   — a direct-inference probe judged against rubrics
    """

    key: str
    kind: str
    task: str
    tags: Tags
    rewards: Rewards
    uri: str | None = None
    created_at: float = field(default_factory=time.time)
