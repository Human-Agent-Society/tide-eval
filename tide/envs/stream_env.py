"""StreamEnv: a continual-learning stream as a Gym-style environment.

Each step is one phase of the stream. The observation carries the phase's
**ingest material** (what your system may learn from) and the **questions**
to answer; the action is your answers; the reward is the fraction judged
correct by the benchmark's deterministic judge.

The env never manages your memory — carrying knowledge across phases is the
learner's job, and exactly what the reward ends up measuring. Two arms make
the measurement honest:

    stateful arm: keep your memory across phases  → the learner's score
    fresh arm:    wipe memory every phase         → the capability control

``metrics.gain`` on the two runs isolates learning from raw capability.
Judged offline and deterministically for the in-repo streams; no API keys.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from tide.envs.core import Observation, StepResult

# (question_record, answer_text) -> 1.0 | 0.0
Judge = Callable[[dict, str], float]


def keyword_judge(record: dict, answer: str) -> float:
    """ocean-facts: the answer must contain the fact's keyword text."""
    return 1.0 if record["metadata"]["answer_keyword"] in answer else 0.0


def expected_lines_judge(record: dict, answer: str) -> float:
    """hidden-rules: every expected 'Round n: LABEL' line must appear."""
    expected = record["metadata"]["expected"]
    hits = sum(f"Round {i + 1}: {label}" in answer for i, label in enumerate(expected))
    return hits / len(expected)


class StreamEnv:
    """A phase-per-step stream over jsonl records.

    ``phases`` is a list of phase dicts: ``{"ingest": <text>,
    "questions": [records...]}`` where each question record has ``messages``
    plus whatever metadata its judge needs. ``cumulative`` re-asks every
    earlier question at each phase (ocean-facts style), which is what makes
    forgetting measurable.
    """

    def __init__(self, phases: list[dict], judge: Judge, *, cumulative: bool = False):
        self._phases = phases
        self._judge = judge
        self._cumulative = cumulative
        self._current = 0

    def reset(self, *, seed: int | None = None) -> tuple[Observation, dict]:
        self._current = 0
        return self._observe(), {"phases": len(self._phases)}

    def step(self, action: list[str]) -> StepResult:
        questions = self._questions()
        if len(action) != len(questions):
            raise ValueError(
                f"phase {self._current} has {len(questions)} questions; "
                f"got {len(action)} answers"
            )
        scores = [self._judge(q, a) for q, a in zip(questions, action, strict=True)]
        reward = sum(scores) / len(scores)
        info = {
            "phase": self._current,
            "per_question": scores,
            "n_questions": len(scores),
        }
        self._current += 1
        terminated = self._current >= len(self._phases)
        obs = None if terminated else self._observe()
        return obs, reward, terminated, False, info

    def close(self) -> None:
        pass

    # ------------------------------------------------------------- helpers

    def _questions(self) -> list[dict]:
        if self._cumulative:
            return [
                q
                for phase in self._phases[: self._current + 1]
                for q in phase["questions"]
            ]
        return self._phases[self._current]["questions"]

    def _observe(self) -> Observation:
        phase = self._phases[self._current]
        return {
            "phase": self._current,
            "ingest": phase["ingest"],
            "questions": [q["messages"] for q in self._questions()],
        }


# ----------------------------------------------------------- constructors


def ocean_facts_env(bench_dir: str | Path) -> StreamEnv:
    bench = Path(bench_dir)
    facts = {
        r["name"]: r["text"]
        for r in map(json.loads, (bench / "facts.jsonl").read_text().splitlines())
    }
    probes = {
        r["metadata"]["fact"]: r
        for r in map(json.loads, (bench / "probes.jsonl").read_text().splitlines())
    }
    order = json.loads((bench / "manifest.json").read_text())["order"]
    phases = [{"ingest": facts[name], "questions": [probes[name]]} for name in order]
    return StreamEnv(phases, keyword_judge, cumulative=True)


def hidden_rules_env(bench_dir: str | Path) -> StreamEnv:
    bench = Path(bench_dir)
    records = [
        json.loads(line) for line in (bench / "episodes.jsonl").read_text().splitlines()
    ]
    phases = []
    for record in records:
        # The message interleaves observations and queries; the observations
        # block is the ingest material, the full message is the question.
        content = record["messages"][0]["content"]
        ingest = content.split("\n\nPredict the outcome")[0]
        phases.append({"ingest": ingest, "questions": [record]})
    return StreamEnv(phases, expected_lines_judge, cumulative=False)
