"""Ledger ingestion: the judge's submission history becomes trace rows.

Under the judge protocol every submission is scored by the judge, so the
ledger is a trusted score-over-time record. The verifier writes it to
``/logs/verifier/ledger.jsonl`` (one ``{"t": <sec>, "score": <x>}`` line
per submission); after the trial this file sits inside the trial
directory, and :func:`load_trace` turns it into :class:`TracePoint`s.
"""

from __future__ import annotations

import json
from pathlib import Path

from tide.types import TracePoint

LEDGER_NAME = "ledger.jsonl"


def parse_ledger(text: str) -> list[TracePoint]:
    """Parse ledger lines, skipping malformed ones."""
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


def find_ledger(root: Path) -> Path | None:
    """Locate a ledger anywhere under a trial directory."""
    if not root.is_dir():
        return None
    hits = sorted(root.rglob(LEDGER_NAME))
    return hits[0] if hits else None


def load_trace(root: Path) -> list[TracePoint]:
    ledger = find_ledger(root)
    if ledger is None:
        return []
    try:
        return parse_ledger(ledger.read_text())
    except OSError:
        return []
