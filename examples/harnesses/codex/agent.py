"""Harbor adapter for Codex Goal mode."""

from __future__ import annotations

import shlex
import tempfile
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent

from examples.harnesses.codex.auth import write_codex_auth
from examples.harnesses.common import (
    REMOTE_ROOT,
    checked,
    model_name,
    parse_usage_jsonl,
    populate_usage_context,
    require_api_key,
)

HERE = Path(__file__).parent
HARNESS_VERSION = "0.2.0"
CODEX_VERSION = "0.147.0"


class CodexGoalHarness(BaseAgent):
    """Run the real persisted Codex ``/goal`` state through app-server."""

    def __init__(
        self,
        *args: Any,
        token_budget: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.token_budget = token_budget

    @staticmethod
    def name() -> str:
        return "codex-goal"

    def version(self) -> str:
        return f"{HARNESS_VERSION}+codex.{CODEX_VERSION}"

    async def setup(self, environment) -> None:
        await checked(
            environment,
            "apt-get update && apt-get install -y --no-install-recommends nodejs npm "
            "&& rm -rf /var/lib/apt/lists/* "
            f"&& npm install -g @openai/codex@{CODEX_VERSION}",
        )
        await environment.upload_dir(
            source_dir=HERE,
            target_dir=str(REMOTE_ROOT / "codex"),
        )
        await checked(
            environment,
            f"python -m pip install --no-cache-dir {REMOTE_ROOT / 'codex'}",
        )

    async def run(self, instruction, environment, context) -> None:
        env = {**self.extra_env, "CODEX_HOME": "/tmp/tide-codex-home"}
        require_api_key(env)
        model = model_name(self.model_name)
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "codex-goal"
            bundle.mkdir()
            (bundle / "objective.txt").write_text(instruction)
            await environment.upload_dir(
                source_dir=tmp,
                target_dir=str(REMOTE_ROOT),
            )
        await write_codex_auth(environment, env)
        usage_path = REMOTE_ROOT / "codex-goal" / "usage.jsonl"
        command = [
            "tide-codex-goal",
            str(REMOTE_ROOT / "codex-goal" / "objective.txt"),
            "--model",
            model,
            "--usage-file",
            str(usage_path),
        ]
        if self.token_budget is not None:
            command.extend(["--token-budget", str(self.token_budget)])
        try:
            await checked(
                environment,
                " ".join(shlex.quote(part) for part in command),
                env=env,
            )
        finally:
            usage = await environment.exec(
                command=f"test -f {usage_path} && cat {usage_path} || true"
            )
            populate_usage_context(
                context,
                parse_usage_jsonl(usage.stdout or ""),
                self.model_name or model,
            )
