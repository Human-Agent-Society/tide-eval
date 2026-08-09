"""The Gym-style loop, end to end, offline — no Docker, no API keys.

Two demos:

1. **A task env**: random search on FunctionMinimization. Every step is
   scored by the task's real grader, locally, in microseconds.
2. **A stream env**: HiddenRules with two hand-written "learners" — one that
   accumulates observations across phases and fits the hidden rule, one that
   only ever sees the current phase. The widening gap between them IS the
   continual-learning measurement (the gain metric).

    python examples/gym_quickstart.py
"""

import random
import re

import tide


def demo_task_env() -> None:
    env = tide.make("tide/FunctionMinimization-v0", max_steps=200)
    env.reset()
    rng = random.Random(0)
    while True:
        action = {"x": rng.uniform(-4, 6), "y": rng.uniform(-4, 6)}
        _, reward, _, truncated, info = env.step(action)
        if truncated:
            break
    print(
        f"random search, 200 steps: best reward {env.best_reward:.4f} "
        f"(origin scores 0.3333, optimum 1.0)"
    )
    print(f"final (trusted): {env.final()}")


def parse_rounds(text: str) -> list[tuple[list[int], str]]:
    """Extract (features, outcome) pairs from an ingest block."""
    rounds = []
    for line in text.splitlines():
        m = re.match(
            r"Round \d+: strength=(\d+), cost=(\d+), speed=(\d+), guile=(\d+)"
            r"(?: -> (WIN|LOSS))?",
            line,
        )
        if m:
            feats = [int(v) for v in m.groups()[:4]]
            rounds.append((feats, m.group(5)))
    return rounds


def rule_learner(observations: list[tuple[list[int], str]], queries) -> str:
    """A tiny learner: score = weighted sum fit by greedy threshold search.
    With few observations it guesses; with many it nails the hidden rule."""

    def predict(weights, threshold, feats):
        return (
            "WIN" if sum(w * f for w, f in zip(weights, feats, strict=True)) > threshold else "LOSS"
        )

    best, best_acc = ([1, 1, 1, 1], 10), -1.0
    candidates = [
        ([a, b, c, d], t)
        for a in (-3, -2, -1, 1, 2, 3)
        for b in (-3, -2, -1, 1, 2, 3)
        for c in (-1, 1, 2)
        for d in (-1, 1, 2)
        for t in (5, 10, 15)
    ]
    labeled = [(f, o) for f, o in observations if o]
    for weights, threshold in candidates:
        acc = sum(predict(weights, threshold, f) == o for f, o in labeled) / max(
            len(labeled), 1
        )
        if acc > best_acc:
            best, best_acc = (weights, threshold), acc
    weights, threshold = best
    return "\n".join(
        f"Round {i + 1}: {predict(weights, threshold, feats)}"
        for i, (feats, _) in enumerate(queries)
    )


def demo_stream_env() -> None:
    for arm in ("stateful", "fresh"):
        env = tide.make("tide/HiddenRules-v0")
        obs, _ = env.reset()
        memory: list = []
        rewards = []
        while True:
            observations = parse_rounds(obs["ingest"])
            if arm == "stateful":
                memory.extend(observations)  # continual learning
                knowledge = memory
            else:
                knowledge = observations  # amnesia: the control arm
            queries = parse_rounds(obs["questions"][0][0]["content"])
            queries = [q for q in queries if q[1] is None]
            answer = rule_learner(knowledge, queries)
            obs, reward, terminated, _, _ = env.step([answer])
            rewards.append(round(reward, 2))
            if terminated:
                break
        print(f"{arm:>8}: per-phase rewards {rewards}")
    print("gain = stateful - fresh; it should widen as observations accumulate.")


if __name__ == "__main__":
    print("== task env: tide/FunctionMinimization-v0 ==")
    demo_task_env()
    print("\n== stream env: tide/HiddenRules-v0 ==")
    demo_stream_env()
