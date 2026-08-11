"""Harbor adapter for OpenEvolve."""

from __future__ import annotations

import json
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent

from examples.harnesses.common import (
    REMOTE_ROOT,
    checked,
    model_name,
    require_api_key,
)
from examples.harnesses.openevolve.config import openevolve_config

HERE = Path(__file__).parent
VERSION = "0.3.2"


class OpenEvolveHarness(BaseAgent):
    """Run OpenEvolve inside the task container against Tide's judge."""

    def __init__(self, *args: Any, iterations: int = 100, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.iterations = iterations

    @staticmethod
    def name() -> str:
        return "openevolve"

    def version(self) -> str:
        return VERSION

    async def setup(self, environment) -> None:
        await checked(
            environment,
            f"python -m pip install --no-cache-dir openevolve=={VERSION}",
        )

    async def run(self, instruction, environment, context) -> None:
        del instruction, context
        env = self.extra_env
        require_api_key(env)
        model = model_name(self.model_name)
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "openevolve"
            bundle.mkdir()
            shutil.copy2(HERE / "initial_program.py", bundle)
            shutil.copy2(HERE / "evaluator.py", bundle)
            config = openevolve_config(model, env.get("OPENAI_BASE_URL"))
            (bundle / "config.yaml").write_text(json.dumps(config, indent=2))
            await environment.upload_dir(
                source_dir=tmp,
                target_dir=str(REMOTE_ROOT),
            )
        remote = REMOTE_ROOT / "openevolve"
        await checked(
            environment,
            " ".join(
                [
                    "openevolve-run",
                    shlex.quote(str(remote / "initial_program.py")),
                    shlex.quote(str(remote / "evaluator.py")),
                    "--config",
                    shlex.quote(str(remote / "config.yaml")),
                    "--iterations",
                    str(self.iterations),
                ]
            ),
            env=env,
        )
