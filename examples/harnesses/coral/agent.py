"""Harbor adapter for CORAL."""

from __future__ import annotations

import json
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any

from examples.harnesses.base import TideHarnessBase
from examples.harnesses.coral.auth import write_codex_auth
from examples.harnesses.coral.config import coral_config

HERE = Path(__file__).parent
HARNESS_VERSION = "0.1.0"
CORAL_VERSION = "0.7.16"
CODEX_VERSION = "0.147.0"


class CoralHarness(TideHarnessBase):
    """Run a multi-agent CORAL organization against Tide's judge."""

    def __init__(self, *args: Any, agents: int = 2, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if agents < 1:
            raise ValueError("agents must be at least 1")
        self.agents = agents

    @staticmethod
    def name() -> str:
        return "coral"

    def version(self) -> str:
        return f"{HARNESS_VERSION}+coral.{CORAL_VERSION}"

    async def setup(self, environment) -> None:
        await self._checked(
            environment,
            "apt-get update && apt-get install -y --no-install-recommends git nodejs npm "
            "&& rm -rf /var/lib/apt/lists/* "
            "&& python -m pip install --no-cache-dir uv "
            f"'coral @ git+https://github.com/Human-Agent-Society/CORAL@v{CORAL_VERSION}' "
            f"&& npm install -g @openai/codex@{CODEX_VERSION}",
        )

    async def run(self, instruction, environment, context) -> None:
        env = {**self.extra_env, "CODEX_HOME": "/tmp/tide-codex-home"}
        self._require_api_key(env)
        model = self._model_name()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "coral"
            bundle.mkdir()
            shutil.copytree(HERE / "grader", bundle / "grader")
            shutil.copy2(HERE / "usage.py", bundle)
            (bundle / "seed").mkdir()
            (bundle / "seed" / "solution.json").write_text(
                json.dumps(
                    {
                        "circles": [
                            [0.25, 0.25, 0.25],
                            [0.75, 0.25, 0.25],
                            [0.50, 0.75, 0.25],
                        ]
                    },
                    indent=2,
                )
                + "\n"
            )
            (bundle / "seed" / "AGENTS.md").write_text(
                "Optimize solution.json. Use `coral eval` only for candidates "
                "worth spending a Tide judge submission on.\n"
            )
            config = coral_config(instruction, model, agents=self.agents)
            (bundle / "task.yaml").write_text(json.dumps(config, indent=2))
            await environment.upload_dir(
                source_dir=tmp,
                target_dir=str(self.remote_root),
            )
        await write_codex_auth(self, environment, env)
        remote = self.remote_root / "coral"
        try:
            await self._checked(
                environment,
                " && ".join(
                    [
                        f"cd {shlex.quote(str(remote / 'seed'))}",
                        "git init",
                        "git config user.name tide-harness",
                        "git config user.email tide-harness@example.invalid",
                        "git add .",
                        "git commit -m seed",
                        f"cd {shlex.quote(str(remote))}",
                        "coral start -c task.yaml",
                    ]
                ),
                env=env,
            )
        finally:
            usage = await environment.exec(
                command=" ".join(
                    [
                        "python",
                        shlex.quote(str(remote / "usage.py")),
                        shlex.quote(str(remote / "results")),
                        shlex.quote(model),
                    ]
                )
            )
            self._populate_usage(context, usage.stdout or "")
