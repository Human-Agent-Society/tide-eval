"""Generator for hidden-rules (seeded, deterministic — the committed
episodes.jsonl comes verbatim from running this).

The latent structure: a hidden linear rule over 4 card features decides
WIN/LOSS. Each phase reveals 8 observed rounds (features → outcome) and asks
the learner to classify 4 unseen query rounds. 8 observations pin the rule
poorly; 48 pin it well — which is exactly what makes this a continual-
learning measurement: a learner that accumulates observations across phases
beats one that sees only the current phase, and the gap (the gain metric)
should widen with every phase.
"""

import json
import random
from pathlib import Path

SEED = 20260809
PHASES = 6
OBS_PER_PHASE = 8
QUERIES_PER_PHASE = 4
WEIGHTS = [3, -2, 1, 2]  # the hidden rule: w·x > 10 → WIN
THRESHOLD = 10
FEATURES = ["strength", "cost", "speed", "guile"]


def outcome(card: list[int]) -> str:
    total = sum(w * v for w, v in zip(WEIGHTS, card, strict=True))
    return "WIN" if total > THRESHOLD else "LOSS"


def card_line(i: int, card: list[int]) -> str:
    stats = ", ".join(f"{f}={v}" for f, v in zip(FEATURES, card, strict=True))
    return f"Round {i}: {stats}"


def main() -> None:
    rng = random.Random(SEED)

    def draw() -> list[int]:
        return [rng.randint(0, 5) for _ in FEATURES]

    episodes = []
    for phase in range(PHASES):
        observations = [draw() for _ in range(OBS_PER_PHASE)]
        queries = [draw() for _ in range(QUERIES_PER_PHASE)]
        obs_text = "\n".join(
            f"{card_line(i + 1, c)} -> {outcome(c)}" for i, c in enumerate(observations)
        )
        query_text = "\n".join(card_line(i + 1, c) for i, c in enumerate(queries))
        question = (
            "You are learning the hidden rules of a card game from observed "
            "rounds.\n\nObserved this session:\n"
            + obs_text
            + "\n\nPredict the outcome of each round below. Answer with one "
            'line per round, exactly "Round <n>: WIN" or "Round <n>: LOSS".\n\n'
            + query_text
        )
        episodes.append(
            {
                "messages": [{"role": "user", "content": question}],
                "rubrics": [
                    f'says "Round {i + 1}: {outcome(c)}"' for i, c in enumerate(queries)
                ],
                "metadata": {
                    "phase": phase,
                    "observations": observations,
                    "queries": queries,
                    "expected": [outcome(c) for c in queries],
                },
            }
        )

    out = Path(__file__).parent / "episodes.jsonl"
    out.write_text("\n".join(json.dumps(e) for e in episodes) + "\n")
    print(f"wrote {len(episodes)} phases to {out}")


if __name__ == "__main__":
    main()
