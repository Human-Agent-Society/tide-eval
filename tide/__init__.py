"""tide — autoresearch and continual-learning evaluation on the Harbor
task standard.

One primitive:

- an **episode** (= one Harbor trial) is one trusted measurement: a Harbor
  task run under an agent, scored by an isolated verifier. The scores the
  agent gave itself along the way (its score log) are recorded as untrusted
  ``trace`` rows next to the trusted one.

Two regimes over it:

- **autoresearch** — one open-ended episode, measured *within*: the anytime
  curve of judge-scored submissions;
- **streams** — a :class:`Stream` of episodes under one carried agent
  state, measured *across*: the learning curve over stream positions.

The public surface is deliberately small: :class:`Lab` runs episodes into an
append-only results store; :class:`Stream` sequences them with carried
state; :mod:`tide.metrics` turns the store into curves. See the README for
the full tour.
"""

from tide import metrics
from tide.budget import Budget
from tide.executors import FakeExecutor, HarborExecutor, LocalExecutor
from tide.lab import Lab
from tide.stream import Stream
from tide.types import EpisodeResult, EpisodeSpec, Row, TracePoint

__version__ = "0.1.0"

__all__ = [
    "Lab",
    "Stream",
    "Budget",
    "HarborExecutor",
    "LocalExecutor",
    "FakeExecutor",
    "EpisodeSpec",
    "EpisodeResult",
    "TracePoint",
    "Row",
    "metrics",
]
