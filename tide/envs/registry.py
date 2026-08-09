"""The env registry: string ids in, envs out — Gym's convention, verbatim.

    env = tide.make("tide/TspTour-v0")
    tide.register("mylab/MyBench-v0", entry_point="mypkg.envs:MyEnv", kwargs={...})
    tide.registry.all_ids()

Ids follow Gym's ``namespace/Name-vN`` convention; bumping N is how a
breaking change to data or scoring stays reproducible. Third-party packages
register envs via the ``tide.envs`` entry-point group: expose a zero-arg
callable that calls :func:`register`, and ``tide.make`` finds it after
``pip install``.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from typing import Any

_ID_RE = re.compile(r"^[\w.-]+/[\w.-]+-v\d+$")


@dataclass(frozen=True)
class EnvSpec:
    id: str
    entry_point: str  # "module.path:ClassName"
    kwargs: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    # Gym-style doc fields; `scripts/gen_env_docs.py` renders these.
    observation_doc: str = ""
    action_doc: str = ""
    reward_doc: str = ""

    def make(self, **overrides: Any):
        module_name, _, attr = self.entry_point.partition(":")
        cls = getattr(importlib.import_module(module_name), attr)
        env = cls(**{**self.kwargs, **overrides})
        env.spec = self
        return env


class Registry:
    def __init__(self) -> None:
        self._specs: dict[str, EnvSpec] = {}
        self._plugins_loaded = False

    def register(self, env_id: str, entry_point: str, **fields: Any) -> None:
        if not _ID_RE.match(env_id):
            raise ValueError(
                f"invalid env id {env_id!r}: use 'namespace/Name-vN' (Gym convention)"
            )
        if env_id in self._specs:
            raise ValueError(f"env id {env_id!r} is already registered")
        self._specs[env_id] = EnvSpec(id=env_id, entry_point=entry_point, **fields)

    def make(self, env_id: str, **overrides: Any):
        if env_id not in self._specs:
            self._load_plugins()
        spec = self._specs.get(env_id)
        if spec is None:
            known = ", ".join(sorted(self._specs)) or "(none)"
            raise KeyError(f"unknown env id {env_id!r}; registered: {known}")
        return spec.make(**overrides)

    def spec(self, env_id: str) -> EnvSpec:
        return self._specs[env_id]

    def all_ids(self) -> list[str]:
        self._load_plugins()
        return sorted(self._specs)

    def _load_plugins(self) -> None:
        """Load third-party registrations from the ``tide.envs`` entry-point
        group (once). Each entry point is a zero-arg callable that registers."""
        if self._plugins_loaded:
            return
        self._plugins_loaded = True
        from importlib.metadata import entry_points

        for ep in entry_points(group="tide.envs"):
            try:
                ep.load()()
            except Exception as exc:  # a broken plugin must not break tide
                import logging

                logging.getLogger("tide").warning(
                    "failed to load tide.envs plugin %r: %s", ep.name, exc
                )


registry = Registry()
register = registry.register
make = registry.make
