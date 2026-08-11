"""Harbor adapter for OpenEvolve."""

from __future__ import annotations

import json
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any

from examples.harnesses.base import TideHarnessBase
from examples.harnesses.openevolve.config import openevolve_config

HERE = Path(__file__).parent
HARNESS_VERSION = "0.1.1"
OPENEVOLVE_VERSION = "0.3.2"


class OpenEvolveHarness(TideHarnessBase):
    """Run OpenEvolve inside the task container against Tide's judge."""

    def __init__(self, *args: Any, iterations: int = 100, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.iterations = iterations

    @staticmethod
    def name() -> str:
        return "openevolve"

    def version(self) -> str:
        return f"{HARNESS_VERSION}+openevolve.{OPENEVOLVE_VERSION}"

    async def setup(self, environment) -> None:
        await self._checked(
            environment,
            f"python -m pip install --no-cache-dir openevolve=={OPENEVOLVE_VERSION}",
        )

    async def run(self, instruction, environment, context) -> None:
        del instruction
        env = self.extra_env
        self._require_api_key(env)
        model = self._model_name()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "openevolve"
            bundle.mkdir()
            shutil.copy2(HERE / "initial_program.py", bundle)
            shutil.copy2(HERE / "evaluator.py", bundle)
            shutil.copy2(HERE / "runner.py", bundle)
            shutil.copy2(HERE / "usage.py", bundle)
            config = openevolve_config(model, env.get("OPENAI_BASE_URL"))
            (bundle / "config.yaml").write_text(json.dumps(config, indent=2))
            await environment.upload_dir(
                source_dir=tmp,
                target_dir=str(self.remote_root),
            )
        remote = self.remote_root / "openevolve"
        usage_path = remote / "usage.jsonl"
        run_env = {
            **env,
            "TIDE_USAGE_FILE": str(usage_path),
        }
        try:
            await self._checked(
                environment,
                " ".join(
                    [
                        "python",
                        shlex.quote(str(remote / "runner.py")),
                        shlex.quote(str(remote / "initial_program.py")),
                        shlex.quote(str(remote / "evaluator.py")),
                        "--config",
                        shlex.quote(str(remote / "config.yaml")),
                        "--iterations",
                        str(self.iterations),
                    ]
                ),
                env=run_env,
            )
        finally:
            usage = await environment.exec(
                command=f"test -f {usage_path} && cat {usage_path} || true"
            )
            self._populate_usage(context, usage.stdout or "")
