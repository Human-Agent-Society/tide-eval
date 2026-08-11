"""Shared utilities for Harbor harness adapters."""

from __future__ import annotations

from pathlib import Path

REMOTE_ROOT = Path("/opt/tide-harness")


async def checked(environment, command: str, *, env: dict[str, str] | None = None):
    """Execute a command and raise with a useful tail when it fails."""
    result = await environment.exec(command=command, env=env)
    if result.return_code != 0:
        detail = (result.stderr or result.stdout or "")[-2_000:]
        raise RuntimeError(f"harness command failed ({result.return_code}): {detail}")
    return result


def model_name(value: str | None) -> str:
    """Normalize Harbor's optional provider-qualified model name."""
    if not value:
        raise ValueError("model_name is required for this harness")
    return value.split("/", 1)[-1]


def require_api_key(env: dict[str, str]) -> None:
    """Require the API key supplied through Harbor's environment mapping."""
    if not env.get("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY must be passed through the Harbor agent's env field"
        )
