"""tide — autoresearch evaluation infrastructure on the Harbor task standard.

One primitive:

- an **episode** (= one Harbor trial) is one trusted measurement: a Harbor
  task run under an agent, scored by an isolated verifier. The scores the
  agent gave itself along the way (its score log) are recorded as untrusted
  ``trace`` rows next to the trusted one.

The public surface is deliberately small: :class:`Lab` runs episodes into an
append-only results store; :mod:`tide.metrics` turns the store into curves.
See the README for the full tour.
"""

from tide import metrics
from tide.executors import FakeExecutor, HarborExecutor
from tide.lab import Lab
from tide.types import EpisodeResult, EpisodeSpec, Row, TracePoint

__version__ = "0.1.0"

__all__ = [
    "Lab",
    "HarborExecutor",
    "FakeExecutor",
    "EpisodeSpec",
    "EpisodeResult",
    "TracePoint",
    "Row",
    "metrics",
]
