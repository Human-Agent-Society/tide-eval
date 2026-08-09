"""Benchmark loaders: turn external corpora into tide objects, one call.

Design rule for this module: a loader depends on the *published format* of a
benchmark and on tide's public types — never on tide internals and never on
the benchmark's own tooling. Anything that needs the benchmark's repo to run
(export scripts, spec compilers) belongs in a converter script under
``examples/``, not here.

Currently shipped:

- :func:`load_rubric_probes` — any JSONL corpus of chat messages + rubric
  lists, which is exactly the published format of Tencent's CL-bench and
  CL-bench Life (1,899 + 405 tasks). Download the JSONL from HuggingFace
  (``tencent/CL-bench``, ``tencent/CL-bench-Life``) and every line becomes a
  :class:`tide.Probe`.

For the ingest-then-probe continual-learning conversion, pair this with
:func:`strip_context`: probe once with the full messages (the ``in_context``
arm, capability upper bound) and once with the context removed (the
``from_state`` arm, after the learner ingested it) —
``metrics.internalization`` reads the pair.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from tide.probe import Probe


def load_rubric_probes(
    jsonl_path: Path | str,
    *,
    id_prefix: str | None = None,
    limit: int | None = None,
) -> list[Probe]:
    """Load a messages+rubrics JSONL corpus (Tencent CL-bench format).

    Each line must be an object with ``messages`` (OpenAI chat format) and
    ``rubrics`` (a list of strings, or of objects carrying
    ``rubric_criteria``). ``metadata``, if present, rides along in
    ``Probe.data``. Lines that don't parse raise — a benchmark file with
    corrupt lines should be loud, not silently smaller.
    """
    path = Path(jsonl_path)
    prefix = id_prefix if id_prefix is not None else path.stem
    probes = []
    for i, record in enumerate(_iter_jsonl(path)):
        if limit is not None and i >= limit:
            break
        probes.append(
            Probe(
                id=f"{prefix}/{i}",
                messages=list(record["messages"]),
                rubrics=tuple(_rubric_text(r) for r in record.get("rubrics", [])),
                data=dict(record.get("metadata", {})),
            )
        )
    return probes


def strip_context(probe: Probe, *, keep_roles: tuple[str, ...] = ("system",)) -> Probe:
    """The from-state arm of ingest-then-probe: drop every message except the
    kept roles and the final user turn (the question itself).

    The removed messages are what the learner should have ingested into its
    state; a learner that internalized them answers anyway.
    """
    if not probe.messages:
        return probe
    kept = [m for m in probe.messages[:-1] if m.get("role") in keep_roles]
    kept.append(probe.messages[-1])
    return Probe(id=probe.id, messages=kept, rubrics=probe.rubrics, data=probe.data)


def _iter_jsonl(path: Path) -> Iterator[dict]:
    with path.open() as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_no}: invalid JSON line") from e


def _rubric_text(rubric: str | dict) -> str:
    if isinstance(rubric, dict):
        return str(rubric.get("rubric_criteria", "")).strip()
    return str(rubric).strip()
