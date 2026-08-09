"""The Env interface: Gym's loop, shaped for LLM continual learning.

The contract mirrors Gymnasium's:

    env = tide.make("tide/HiddenRules-v0")
    obs, info = env.reset()
    while True:
        action = my_system(obs)                       # your LLM + your memory
        obs, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break

What differs from classic RL is only the payload types: an observation is a
dict of text (instruction, ingest material, questions); an action is your
system's answer (a solution object or a list of answer strings); the reward
comes from the same trusted graders the containerized pipeline uses.

State is deliberately YOURS to keep. A continual-learning env never manages
your memory — it feeds you material phase by phase and measures what stuck.
That is the measurement, and the env's whole job.
"""

from __future__ import annotations

from typing import Any, Protocol

Observation = dict[str, Any]
StepResult = tuple[Observation | None, float, bool, bool, dict[str, Any]]


class Env(Protocol):
    """The five-method surface every tide env implements."""

    spec: Any  # the registry EnvSpec that made this env

    def reset(self, *, seed: int | None = None) -> tuple[Observation, dict]:
        """Start (or restart) the env. Returns (observation, info)."""
        ...

    def step(self, action: Any) -> StepResult:
        """Advance one step. Returns (obs, reward, terminated, truncated, info).

        ``terminated``: the env's sequence is exhausted (a stream ran out of
        phases). ``truncated``: a budget you set (``max_steps``) ran out.
        """
        ...

    def close(self) -> None: ...
