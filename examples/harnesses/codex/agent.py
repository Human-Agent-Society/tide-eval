"""Version-pinned Harbor Codex adapter."""

from __future__ import annotations

from typing import Any

from harbor.agents.installed.codex import Codex

CODEX_VERSION = "0.147.0"


class CodexHarness(Codex):
    """Use Harbor's standard non-interactive Codex agent at a fixed version."""

    def __init__(
        self,
        *args: Any,
        version: str = CODEX_VERSION,
        **kwargs: Any,
    ) -> None:
        if version != CODEX_VERSION:
            raise ValueError(f"CodexHarness requires Codex {CODEX_VERSION}")
        super().__init__(*args, version=version, **kwargs)
