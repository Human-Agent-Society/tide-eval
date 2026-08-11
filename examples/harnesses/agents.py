"""Harbor adapters for OpenEvolve, Codex Goal mode, and CORAL."""

from __future__ import annotations

import json
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent

from examples.harnesses.config import coral_config, openevolve_config

HERE = Path(__file__).parent
REMOTE_ROOT = Path("/opt/tide-harness")
OPENEVOLVE_VERSION = "0.3.2"
CODEX_HARNESS_VERSION = "0.1.0"
CODEX_VERSION = "0.147.0"
CORAL_VERSION = "0.7.16"


async def _checked(environment, command: str, *, env: dict[str, str] | None = None):
    result = await environment.exec(command=command, env=env)
    if result.return_code != 0:
        detail = (result.stderr or result.stdout or "")[-2_000:]
        raise RuntimeError(f"harness command failed ({result.return_code}): {detail}")
    return result


def _model_name(model_name: str | None) -> str:
    if not model_name:
        raise ValueError("model_name is required for this harness")
    return model_name.split("/", 1)[-1]


def _require_api_key(env: dict[str, str]) -> None:
    if not env.get("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY must be passed through the Harbor agent's env field"
        )


class OpenEvolveHarness(BaseAgent):
    """Run OpenEvolve inside the task container against Tide's judge."""

    def __init__(self, *args: Any, iterations: int = 100, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.iterations = iterations

    @staticmethod
    def name() -> str:
        return "openevolve"

    def version(self) -> str:
        return OPENEVOLVE_VERSION

    async def setup(self, environment) -> None:
        await _checked(
            environment,
            f"python -m pip install --no-cache-dir openevolve=={OPENEVOLVE_VERSION}",
        )

    async def run(self, instruction, environment, context) -> None:
        del instruction, context
        env = self.extra_env
        _require_api_key(env)
        model = _model_name(self.model_name)
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "openevolve"
            shutil.copytree(HERE / "openevolve", bundle)
            config = openevolve_config(model, env.get("OPENAI_BASE_URL"))
            (bundle / "config.yaml").write_text(json.dumps(config, indent=2))
            await environment.upload_dir(
                source_dir=tmp,
                target_dir=str(REMOTE_ROOT),
            )
        remote = REMOTE_ROOT / "openevolve"
        await _checked(
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
        return f"{CODEX_HARNESS_VERSION}+codex.{CODEX_VERSION}"

    async def setup(self, environment) -> None:
        await _checked(
            environment,
            "apt-get update && apt-get install -y --no-install-recommends nodejs npm "
            "&& rm -rf /var/lib/apt/lists/* "
            f"&& npm install -g @openai/codex@{CODEX_VERSION}",
        )
        await environment.upload_dir(
            source_dir=HERE / "codex",
            target_dir=str(REMOTE_ROOT / "codex"),
        )
        await _checked(
            environment,
            f"python -m pip install --no-cache-dir {REMOTE_ROOT / 'codex'}",
        )

    async def run(self, instruction, environment, context) -> None:
        del context
        env = {**self.extra_env, "CODEX_HOME": "/tmp/tide-codex-home"}
        _require_api_key(env)
        model = _model_name(self.model_name)
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "codex-goal"
            bundle.mkdir()
            (bundle / "objective.txt").write_text(instruction)
            await environment.upload_dir(
                source_dir=tmp,
                target_dir=str(REMOTE_ROOT),
            )
        await _write_codex_auth(environment, env)
        command = [
            "tide-codex-goal",
            str(REMOTE_ROOT / "codex-goal" / "objective.txt"),
            "--model",
            model,
        ]
        if self.token_budget is not None:
            command.extend(["--token-budget", str(self.token_budget)])
        await _checked(
            environment,
            " ".join(shlex.quote(part) for part in command),
            env=env,
        )


class CoralHarness(BaseAgent):
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
        return CORAL_VERSION

    async def setup(self, environment) -> None:
        await _checked(
            environment,
            "apt-get update && apt-get install -y --no-install-recommends git nodejs npm "
            "&& rm -rf /var/lib/apt/lists/* "
            "&& python -m pip install --no-cache-dir uv "
            f"'coral @ git+https://github.com/Human-Agent-Society/CORAL@v{CORAL_VERSION}' "
            f"&& npm install -g @openai/codex@{CODEX_VERSION}",
        )

    async def run(self, instruction, environment, context) -> None:
        del context
        env = {**self.extra_env, "CODEX_HOME": "/tmp/tide-codex-home"}
        _require_api_key(env)
        model = _model_name(self.model_name)
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "coral"
            shutil.copytree(HERE / "coral", bundle)
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
                target_dir=str(REMOTE_ROOT),
            )
        await _write_codex_auth(environment, env)
        remote = REMOTE_ROOT / "coral"
        await _checked(
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


async def _write_codex_auth(environment, env: dict[str, str]) -> None:
    command = """python - <<'PY'
import json
import os
from pathlib import Path

home = Path(os.environ["CODEX_HOME"])
home.mkdir(parents=True, exist_ok=True)
(home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": os.environ["OPENAI_API_KEY"]}))
PY"""
    await _checked(environment, command, env=env)
