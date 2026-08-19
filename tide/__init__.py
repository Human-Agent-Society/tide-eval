"""tide: autoresearch and continual-learning evaluation on the Harbor
task standard.

One primitive, the episode (one Harbor trial): a task run under an agent
and scored by an isolated verifier. The judge's score for every submission
along the way is recorded as ``trace`` rows beside it.

Two regimes on top. Autoresearch measures learning within one open-ended
episode (the anytime curve of judge-scored submissions); streams measure
what carries into later tasks (a :class:`Stream` of episodes under one
carried agent state).

:class:`Lab` runs episodes into an append-only results store,
:class:`Stream` sequences them with carried state, and
:mod:`tide.metrics` turns the store into curves.
"""

from tide import metrics
from tide.budget import Budget
from tide.executors import FakeExecutor, HarborExecutor, LocalExecutor
from tide.lab import Lab
from tide.stream import Stream
from tide.targets import tasks
from tide.types import EpisodeResult, EpisodeSpec, Row, TracePoint

__version__ = "0.1.0"

__all__ = [
    "Lab",
    "Stream",
    "tasks",
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
