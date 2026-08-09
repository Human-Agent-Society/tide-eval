"""tide — continual evaluation infrastructure on the Harbor task standard.

Two primitives:

- an **episode** is one trusted measurement (a Harbor task run under an agent);
- a **stream** is an ordered sequence of episodes where a single state folder
  is the only thing that crosses the boundaries.

The public surface is deliberately small: :class:`Lab` runs episodes and
probes into an append-only results store; :mod:`tide.metrics` turns the store
into curves and matrices; :mod:`tide.stream` provides the state machinery
stream scripts need. See the README for the full tour.
"""

from tide import metrics
from tide.executors import FakeExecutor, HarborExecutor
from tide.lab import Lab
from tide.probe import Probe, ProbeExecutor
from tide.stream import StateDir, StaticWeightPlane, WeightPlane
from tide.types import EpisodeResult, EpisodeSpec, Row, TracePoint

__all__ = [
    "Lab",
    "Probe",
    "ProbeExecutor",
    "HarborExecutor",
    "FakeExecutor",
    "StateDir",
    "WeightPlane",
    "StaticWeightPlane",
    "EpisodeSpec",
    "EpisodeResult",
    "TracePoint",
    "Row",
    "metrics",
]
