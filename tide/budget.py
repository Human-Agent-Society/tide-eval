"""Budget: how much an episode is allowed to spend.

A budget is more than a clock. Autoresearch runs are bounded by whichever
resource is scarce — wall-clock **time**, the number of judge **evaluations**
(submissions), the **tokens** an LLM burns, or the **dollars** it costs — and
"what does 2x the budget buy?" is a question about any of them.

tide models all four uniformly. Each dimension is:

- **set** on the run (this object),
- **delivered** to the agent as a ``TIDE_*`` environment variable so a harness
  or method can pace itself against it (see :meth:`Budget.to_env`), and
- **recorded** as a ``budget_*`` tag so runs group and pivot by it
  (see :meth:`Budget.to_tags`); the *actual* spend comes back as ``used_*``
  columns (see :class:`tide.types.EpisodeResult` ``usage``).

Enforcement differs by dimension, and the docs are honest about it:

- ``time_h`` is **hard** — it becomes the container timeout, so the episode is
  killed at the deadline (a normal ending; the verifier still grades the
  best-so-far).
- ``max_submissions`` is enforced **hard by the judge** only up to the task's
  own ``judge_config.json`` ceiling; a *lower* per-run value is a signal the
  agent is asked to honor (Harbor cannot inject env into the judge sidecar).
- ``max_tokens`` / ``max_cost_usd`` are **soft** signals — tide cannot halt a
  black-box harness mid-generation, so it passes the limit to the agent and
  records the true spend regardless.

The scarce dimension is the one you set; leave the rest ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Budget:
    time_h: float | None = None
    max_submissions: int | None = None
    max_tokens: int | None = None
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        for name in ("time_h", "max_submissions", "max_tokens", "max_cost_usd"):
            v = getattr(self, name)
            if v is not None and v <= 0:
                raise ValueError(f"budget {name} must be positive, got {v!r}")

    @property
    def is_empty(self) -> bool:
        return not any(
            v is not None
            for v in (
                self.time_h,
                self.max_submissions,
                self.max_tokens,
                self.max_cost_usd,
            )
        )

    def timeout_sec(self) -> float | None:
        """The wall-clock budget as seconds — the container/`--local` timeout."""
        return None if self.time_h is None else self.time_h * 3600.0

    def to_env(self) -> dict[str, str]:
        """Budget signals for the agent's container, mirroring ``$BUDGET_SEC``.

        A harness or method reads these to pace itself; ignoring them only
        means the run spends more, which ``used_*`` will show.
        """
        env: dict[str, str] = {}
        if self.time_h is not None:
            env["TIDE_BUDGET_SEC"] = repr(self.timeout_sec())
        if self.max_submissions is not None:
            env["TIDE_MAX_SUBMISSIONS"] = str(self.max_submissions)
        if self.max_tokens is not None:
            env["TIDE_MAX_TOKENS"] = str(self.max_tokens)
        if self.max_cost_usd is not None:
            env["TIDE_MAX_COST_USD"] = repr(self.max_cost_usd)
        return env

    def to_tags(self) -> dict[str, Any]:
        """The budget as grouping tags. ``budget`` stays the hours value for
        back-compat with existing scaling queries; the rest are explicit."""
        tags: dict[str, Any] = {}
        if self.time_h is not None:
            tags["budget"] = self.time_h
            tags["budget_time_h"] = self.time_h
        if self.max_submissions is not None:
            tags["budget_max_submissions"] = self.max_submissions
        if self.max_tokens is not None:
            tags["budget_max_tokens"] = self.max_tokens
        if self.max_cost_usd is not None:
            tags["budget_max_cost_usd"] = self.max_cost_usd
        return tags

    @classmethod
    def coerce(
        cls, value: Budget | dict[str, Any] | float | int | None
    ) -> Budget | None:
        """Accept a Budget, a dict of its fields, or a bare number (= hours)."""
        if value is None or isinstance(value, cls):
            return value
        if isinstance(value, (int, float)):
            return cls(time_h=float(value))
        if isinstance(value, dict):
            allowed = {"time_h", "max_submissions", "max_tokens", "max_cost_usd"}
            unknown = set(value) - allowed
            if unknown:
                raise ValueError(f"unknown budget fields: {sorted(unknown)}")
            return cls(**value)
        raise TypeError(f"cannot coerce {value!r} to Budget")
