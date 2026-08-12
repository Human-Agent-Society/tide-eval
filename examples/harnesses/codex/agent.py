"""Version-pinned Harbor Codex adapter."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex

CODEX_VERSION = "0.147.0"

HERE = Path(__file__).parent
REMOTE_FINALIZE = "/tmp/tide_codex_finalize.py"


class CodexHarness(Codex):
    """Use Harbor's standard non-interactive Codex agent at a fixed version.

    ``final_artifact`` (default ``"solution.json"``, relative to the task
    image's workdir; pass ``None`` to disable) is the workspace file the
    task's judge scores. After the agent stops — a timeout included, which
    this protocol treats as a normal ending — the harness submits that file
    to the judge *only if the agent never submitted anything*: the verifier
    grades the judge's submission log, so without this fallback a run that
    never called ``$JUDGE_URL/submit`` scores 0.0 regardless of what it
    left in the workspace. When the agent did submit, best-of semantics
    already cover the run and the fallback stays out of the way.
    """

    def __init__(
        self,
        *args: Any,
        version: str = CODEX_VERSION,
        final_artifact: str | None = "solution.json",
        **kwargs: Any,
    ) -> None:
        if version != CODEX_VERSION:
            raise ValueError(f"CodexHarness requires Codex {CODEX_VERSION}")
        super().__init__(*args, version=version, **kwargs)
        self.final_artifact = final_artifact

    async def run(self, instruction, environment, context) -> None:
        try:
            await super().run(instruction, environment, context)
        finally:
            if self.final_artifact is not None:
                await self._submit_final_artifact(environment)

    async def _submit_final_artifact(self, environment) -> None:
        """Submit the final artifact if the judge saw zero submissions.

        Best-effort: a failure here must never fail the trial.
        """
        try:
            await environment.upload_file(HERE / "finalize.py", REMOTE_FINALIZE)
            workdir = ((await environment.exec(command="pwd")).stdout or "").strip()
            artifact = self.final_artifact
            if not artifact.startswith("/"):
                artifact = f"{workdir.rstrip('/')}/{artifact}"
            await environment.exec(
                command=f"python3 {REMOTE_FINALIZE} {shlex.quote(artifact)}"
            )
        except Exception:
            self.logger.warning("codex final-artifact fallback failed", exc_info=True)
