"""Benchmark loaders: turn external corpora into tide objects, one call.

Design rule for this module: a loader depends on the *published format* of a
benchmark and on tide's public types — never on tide internals and never on
the benchmark's own tooling. Anything that needs the benchmark's repo to run
(export scripts, spec compilers) belongs in a converter script under
``examples/``, not here.

Currently shipped:

- :func:`load_rubric_probes` — any JSONL corpus of chat messages + rubric
  lists (each line becomes a :class:`tide.Probe`); the in-repo stream
  benchmarks under ``tasks/streams/`` ship probes in this format.
- :func:`load_clbench_results` — Continual-Learning-Bench run results into a
  metrics-ready DataFrame.

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
    """Load a messages+rubrics JSONL corpus into probes.

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


def reveal_phases(
    probe: Probe,
    n: int,
    *,
    keep_roles: tuple[str, ...] = ("system",),
) -> list[Probe]:
    """AgentStream-style progressive reveal: turn one probe into a stream.

    The probe's context (everything except kept roles and the final question)
    is split into *n* contiguous chunks; phase ``i`` reveals chunks ``0..i``,
    so the last phase equals the original probe. Probing the same question at
    every phase yields the checkpoint curve AgentStream measures — how
    performance improves as information arrives.

    Chunking: when the context spans at least *n* messages, split by message;
    a single long context message is split by paragraphs instead.

    Returned probes are ids ``<id>@r0 .. <id>@r{n-1}`` with rubrics and data
    unchanged. Pair with ``strip_context`` + a learner ingesting each newly
    revealed chunk for the stateful arm.
    """
    if n < 1:
        raise ValueError("reveal_phases needs n >= 1")
    if not probe.messages:
        return [probe]

    kept = [m for m in probe.messages[:-1] if m.get("role") in keep_roles]
    context = [m for m in probe.messages[:-1] if m.get("role") not in keep_roles]
    question = probe.messages[-1]
    if not context:
        return [probe]  # nothing to reveal progressively

    if len(context) >= n:
        chunks = _split_even(context, n)
    else:
        text = "\n\n".join(m.get("content", "") for m in context)
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        chunks = [
            [
                {
                    "role": "user",
                    "content": f"[context part {i + 1}/{n}]\n" + "\n\n".join(group),
                }
            ]
            for i, group in enumerate(_split_even(paragraphs, n))
        ]

    phases = []
    for i in range(len(chunks)):
        revealed = [m for chunk in chunks[: i + 1] for m in chunk]
        phases.append(
            Probe(
                id=f"{probe.id}@r{i}",
                messages=[*kept, *revealed, question],
                rubrics=probe.rubrics,
                data=probe.data,
            )
        )
    return phases


def _split_even(items: list, n: int) -> list[list]:
    """Split *items* into at most *n* contiguous, non-empty, near-equal groups."""
    n = min(n, len(items))
    base, extra = divmod(len(items), n)
    groups, start = [], 0
    for i in range(n):
        size = base + (1 if i < extra else 0)
        groups.append(items[start : start + size])
        start += size
    return groups


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


def load_clbench_results(runs_dir: Path | str) -> pd.DataFrame:  # noqa: F821
    """Load Continual-Learning-Bench run results into a metrics-ready frame.

    ``runs_dir`` is a CLB ``final_results/runs/`` directory (produced by
    their harness, or downloaded from their repo). Returns one row per
    instance outcome with columns: ``run · system · model · task ·
    schedule · run_index · instance_index · instance_id · reward · success ·
    variant`` — which feeds :mod:`tide.metrics` directly::

        df = load_clbench_results("continual-learning-bench/final_results/runs")
        curves = metrics.anytime(df, time="instance_index", score="reward",
                                 by=["system", "task"])

    tide never redistributes their data (note the benchmark's canary): this
    loads results you generated or fetched locally.
    """
    import gzip

    import pandas as pd

    rows = []
    for manifest_path in sorted(Path(runs_dir).glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text())
        system = manifest.get("system", "")
        args = manifest.get("system_args") or []
        model = ""
        for i, arg in enumerate(args):
            if arg == "--system.model" and i + 1 < len(args):
                model = args[i + 1]
        for entry in manifest.get("tasks", []):
            gz = manifest_path.parent / "tasks" / f"{entry['task']}.json.gz"
            if not gz.exists():
                continue
            with gzip.open(gz, "rt") as f:
                payload = json.loads(f.read())
            for run in payload.get("run_traces", []):
                trace = run.get("trace", {})
                for outcome in trace.get("instance_outcomes", []):
                    rows.append(
                        {
                            "run": manifest.get("run_name", manifest_path.parent.name),
                            "system": system,
                            "model": model,
                            "task": entry["task"],
                            "schedule": entry.get("schedule", ""),
                            "run_index": run.get("run_index"),
                            "instance_index": outcome.get("instance_index"),
                            "instance_id": outcome.get("instance_id", ""),
                            "reward": outcome.get("reward"),
                            "success": outcome.get("success"),
                            "variant": (outcome.get("metadata") or {}).get(
                                "variant_id", ""
                            ),
                        }
                    )
    return pd.DataFrame(rows)
