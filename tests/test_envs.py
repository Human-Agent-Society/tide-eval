"""The Gym-style surface: registry contract + every built-in env's semantics.

Task envs are checked against the same vectors.json files as the container
pipeline — one grading truth, two surfaces.
"""

import json
from pathlib import Path

import pytest

import tide

TASKS_ROOT = Path(__file__).parent.parent / "tasks"

TASK_ENVS = {
    "tide/CirclePacking-v0": "autoresearch/circle-packing",
    "tide/FunctionMinimization-v0": "autoresearch/function-minimization",
    "tide/TspTour-v0": "autoresearch/tsp-tour",
    "tide/BinPacking-v0": "autoresearch/bin-packing",
    "tide/StringCompression-v0": "autoresearch/string-compression",
}


# ------------------------------------------------------------------ registry


def test_all_builtins_registered():
    ids = tide.envs.registry.all_ids()
    assert set(TASK_ENVS) <= set(ids)
    assert {
        "tide/SymbolicRegression-v0",
        "tide/OceanFacts-v0",
        "tide/HiddenRules-v0",
    } <= set(ids)


def test_invalid_id_and_duplicates_are_loud():
    with pytest.raises(ValueError, match="namespace/Name-vN"):
        tide.register("not-an-id", entry_point="x:y")
    with pytest.raises(ValueError, match="already registered"):
        tide.register("tide/TspTour-v0", entry_point="x:y")
    with pytest.raises(KeyError, match="unknown env id"):
        tide.make("tide/Nonsense-v0")


def test_spec_carries_docs():
    spec = tide.envs.registry.spec("tide/OceanFacts-v0")
    assert spec.description and spec.reward_doc and spec.action_doc


# ----------------------------------------------------------------- task envs


@pytest.mark.parametrize("env_id", sorted(TASK_ENVS), ids=lambda s: s.split("/")[1])
def test_task_env_matches_vectors(env_id):
    """step() on the oracle artifact reproduces the pinned vector reward;
    every cheat scores 0 — the env and the container share one grader."""
    vectors = json.loads(
        (TASKS_ROOT / TASK_ENVS[env_id] / "tests" / "vectors.json").read_text()
    )
    env = tide.make(env_id)
    obs, info = env.reset()
    assert obs["instruction"]

    _, reward, terminated, truncated, step_info = env.step(
        vectors["oracle"]["artifact"]
    )
    oracle = vectors["oracle"]
    if "reward" in oracle:
        assert reward == pytest.approx(
            oracle["reward"], abs=oracle.get("tolerance", 1e-9)
        )
    else:
        assert oracle["reward_min"] <= reward <= oracle["reward_max"]
    assert not terminated and not truncated

    for cheat in vectors["cheats"]:
        _, cheat_reward, *_ = env.step(cheat["artifact"])
        assert cheat_reward == 0.0, cheat["name"]

    # best-so-far survived the cheats; final() re-grades it trusted
    assert env.final()["reward"] == pytest.approx(reward, abs=1e-6)


def test_task_env_truncates_at_max_steps():
    env = tide.make("tide/FunctionMinimization-v0", max_steps=2)
    env.reset()
    _, _, _, truncated, _ = env.step({"x": 0.0, "y": 0.0})
    assert not truncated
    _, _, _, truncated, _ = env.step({"x": 0.5, "y": 0.5})
    assert truncated


def test_symbolic_regression_wall_survives_gym_mode():
    env = tide.make("tide/SymbolicRegression-v0")
    env.reset()
    # a memorizing-style expression can look decent on train...
    _, train_reward, *_ = env.step({"expr": "0.5 * x**2"})
    assert train_reward == pytest.approx(0.5808, abs=1e-3)  # train-only score
    # ...but final() grades held-out: the true structure wins outright
    env.step({"expr": "0.5 * x**2 + sin(x)"})
    assert env.final()["reward"] == pytest.approx(1.0, abs=1e-6)


def test_task_env_final_without_steps():
    env = tide.make("tide/TspTour-v0")
    env.reset()
    assert env.final()["reward"] == 0.0


# --------------------------------------------------------------- stream envs


def test_hidden_rules_perfect_and_ignorant_policies():
    records = [
        json.loads(line)
        for line in (TASKS_ROOT / "streams/hidden-rules/episodes.jsonl")
        .read_text()
        .splitlines()
    ]
    env = tide.make("tide/HiddenRules-v0")
    obs, info = env.reset()
    assert info["phases"] == len(records)

    rewards = []
    for record in records:
        answer = "\n".join(
            f"Round {i + 1}: {label}"
            for i, label in enumerate(record["metadata"]["expected"])
        )
        obs, reward, terminated, _, _ = env.step([answer])
        rewards.append(reward)
    assert rewards == [1.0] * len(records) and terminated

    env.reset()
    _, reward, *_ = env.step(["I refuse to answer"])
    assert reward == 0.0


def test_ocean_facts_cumulative_questions_and_memory_gain():
    env = tide.make("tide/OceanFacts-v0")
    obs, _ = env.reset()
    assert len(obs["questions"]) == 1

    # A perfect-memory learner: answer every question with every ingested fact.
    memory = []
    rewards = []
    while True:
        memory.append(obs["ingest"])
        answers = ["\n".join(memory)] * len(obs["questions"])
        obs, reward, terminated, _, info = env.step(answers)
        rewards.append(reward)
        if terminated:
            break
    assert rewards[-1] == 1.0  # remembered everything, cumulative probe passes
    assert info["n_questions"] == 8  # last phase re-asked all 8

    # The fresh control: no memory, only the current ingest — forgets the past.
    obs, _ = env.reset()
    obs, reward, *_ = env.step([obs["ingest"]])
    obs, reward, *_ = env.step([obs["ingest"]] * len(obs["questions"]))
    assert reward == pytest.approx(0.5)  # knows fact 2, forgot fact 1


def test_stream_answer_count_mismatch_is_loud():
    env = tide.make("tide/OceanFacts-v0")
    env.reset()
    with pytest.raises(ValueError, match="1 questions"):
        env.step(["a", "b", "c"])
