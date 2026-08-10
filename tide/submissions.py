"""Submission-log ingestion: the judge's history becomes trace rows.

Every submission is scored by the judge, so the submission log is a
trusted score-over-time record. The verifier writes it to
``/logs/verifier/submissions.jsonl`` (one ``{"t": <sec>, "score": <x>}``
line per submission); after the trial this file sits inside the trial
directory, and :func:`load_trace` turns it into :class:`TracePoint`s.
"""

from __future__ import annotations

import json
from pathlib import Path

from tide.types import TracePoint

SUBMISSIONS_LOG = "submissions.jsonl"


def parse_submissions(text: str) -> list[TracePoint]:
    """Parse submission-log lines, skipping malformed ones."""
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


def find_submissions_log(root: Path) -> Path | None:
    """Locate a submission log anywhere under a trial directory."""
    if not root.is_dir():
        return None
    hits = sorted(root.rglob(SUBMISSIONS_LOG))
    return hits[0] if hits else None


def load_trace(root: Path) -> list[TracePoint]:
    log = find_submissions_log(root)
    if log is None:
        return []
    try:
        return parse_submissions(log.read_text())
    except OSError:
        return []
