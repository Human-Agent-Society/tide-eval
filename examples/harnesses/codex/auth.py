"""Codex authentication setup inside a Harbor task container."""

from __future__ import annotations

from examples.harnesses.common import checked


async def write_codex_auth(environment, env: dict[str, str]) -> None:
    command = """python - <<'PY'
import json
import os
from pathlib import Path

home = Path(os.environ["CODEX_HOME"])
home.mkdir(parents=True, exist_ok=True)
(home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": os.environ["OPENAI_API_KEY"]}))
PY"""
    await checked(environment, command, env=env)
