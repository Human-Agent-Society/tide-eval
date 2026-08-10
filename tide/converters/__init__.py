"""Benchmark converters: published spec formats → stock Harbor task dirs.

A converter depends only on the published format and tide's public types —
never on a benchmark's own tooling. Whatever a converter emits must validate
under Harbor's `TaskConfig` and run standalone with `harbor trial start`.
"""

from tide.converters.edgebench import convert_edgebench_task

__all__ = ["convert_edgebench_task"]
