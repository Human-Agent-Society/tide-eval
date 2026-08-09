"""tide.envs — the Gym-style surface: string ids in, environments out."""

from tide.envs import (
    registrations as _registrations,  # noqa: F401  (registers built-ins)
)
from tide.envs.core import Env, Observation, StepResult
from tide.envs.registry import EnvSpec, make, register, registry
from tide.envs.stream_env import StreamEnv
from tide.envs.task_env import TaskEnv

__all__ = [
    "Env",
    "EnvSpec",
    "Observation",
    "StepResult",
    "StreamEnv",
    "TaskEnv",
    "make",
    "register",
    "registry",
]
