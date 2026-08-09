"""Score-trajectory ingestion: the one piece of real autoresearch machinery.

The task convention: an agent that self-evaluates appends one JSON line per
evaluation to ``score_log.jsonl`` inside the episode's artifact directory::

    {"t": 12.5, "score": 0.31}
    {"t": 90.2, "score": 0.47, "snapshot": "best_003.json"}

``t`` is seconds since the episode started; extra keys ride along untouched.
These numbers are **untrusted** (the agent wrote them); tide stores them as
``trace`` rows so anytime/progress curves are queryable, while the trusted
verdict for the episode remains the verifier's ``episode`` row. Tasks that
archive timestamped snapshots can have the verifier re-score them, replacing
the claimed curve with a trusted one — that recomputation still flows through
this same format.
"""

from __future__ import annotations

import json
from pathlib import Path

from tide.types import TracePoint

SCORE_LOG_NAME = "score_log.jsonl"


def parse_score_log(text: str) -> list[TracePoint]:
    """Parse score-log lines, skipping malformed ones.

    Lenient by design: the log is agent-written and an episode should never
    fail to record because the agent wrote one bad line.
    """
    points: list[TracePoint] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            t = float(obj.pop("t"))
            score = float(obj.pop("score"))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        points.append(TracePoint(t=t, score=score, data=obj))
    points.sort(key=lambda p: p.t)
    return points


def find_score_log(artifacts_dir: Path) -> Path | None:
    """Locate a score log anywhere under an artifacts directory.

    Harbor mirrors the agent's publish dir to a nested host path
    (``artifacts/logs/artifacts/``), so we search rather than assume a level.
    """
    if not artifacts_dir.is_dir():
        return None
    hits = sorted(artifacts_dir.rglob(SCORE_LOG_NAME))
    return hits[0] if hits else None


def load_trace(artifacts_dir: Path) -> list[TracePoint]:
    log = find_score_log(artifacts_dir)
    if log is None:
        return []
    try:
        return parse_score_log(log.read_text())
    except OSError:
        return []
