"""Shared Harbor base class for Tide harness adapters."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent


class TideHarnessBase(BaseAgent):
    """Common Harbor lifecycle utilities for Tide's custom harnesses."""

    remote_root = Path("/opt/tide-harness")

    async def _checked(
        self,
        environment,
        command: str,
        *,
        env: dict[str, str] | None = None,
    ):
        """Execute a command and raise with a useful tail when it fails."""
        result = await environment.exec(command=command, env=env)
        if result.return_code != 0:
            detail = (result.stderr or result.stdout or "")[-2_000:]
            raise RuntimeError(
                f"harness command failed ({result.return_code}): {detail}"
            )
        return result

    def _model_name(self) -> str:
        """Normalize Harbor's optional provider-qualified model name."""
        if not self.model_name:
            raise ValueError("model_name is required for this harness")
        return self.model_name.split("/", 1)[-1]

    @staticmethod
    def _require_api_key(env: dict[str, str]) -> None:
        """Require the API key supplied through Harbor's environment mapping."""
        if not env.get("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY must be passed through the Harbor agent's env field"
            )

    def _populate_usage(self, context, value: str) -> None:
        """Populate Harbor's standard token and cost fields from JSONL output."""
        records = _parse_usage_jsonl(value)
        if not records:
            return
        default_model = self.model_name or self._model_name()
        _populate_usage_context(context, records, default_model)


def _parse_usage_jsonl(value: str) -> list[dict[str, Any]]:
    """Parse normalized token-usage records from mixed command output."""
    records: list[dict[str, Any]] = []
    for line in value.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and all(
            isinstance(record.get(field), int) and record[field] >= 0
            for field in ("input_tokens", "cached_input_tokens", "output_tokens")
        ):
            records.append(record)
    return records


def _populate_usage_context(
    context,
    records: list[dict[str, Any]],
    default_model: str,
) -> None:
    """Populate Harbor's standard token and cost fields from usage records."""
    if not records:
        return

    context.n_input_tokens = sum(record["input_tokens"] for record in records)
    context.n_cache_tokens = sum(record["cached_input_tokens"] for record in records)
    context.n_output_tokens = sum(record["output_tokens"] for record in records)

    total_cost = 0.0
    missing_prices: set[str] = set()
    for record in records:
        model = str(record.get("model") or default_model)
        cost = _cost_from_litellm(
            model=model,
            default_model=default_model,
            input_tokens=record["input_tokens"],
            cached_input_tokens=record["cached_input_tokens"],
            output_tokens=record["output_tokens"],
        )
        if cost is None:
            missing_prices.add(model)
        else:
            total_cost += cost

    metadata = dict(context.metadata or {})
    metadata["usage_records"] = len(records)
    try:
        metadata["pricing_source"] = f"litellm/{version('litellm')}"
    except PackageNotFoundError:
        metadata["pricing_source"] = "unavailable"
    if missing_prices:
        metadata["cost_unavailable_for_models"] = sorted(missing_prices)
    else:
        context.cost_usd = total_cost
        metadata["cost_usd_is_estimate"] = True
    context.metadata = metadata


def _cost_from_litellm(
    *,
    model: str,
    default_model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Estimate API cost without treating cached input as full-price input."""
    try:
        import litellm
    except ImportError:
        return None

    candidates = [model, default_model]
    if "/" in default_model and "/" not in model:
        provider = default_model.split("/", 1)[0]
        candidates.insert(0, f"{provider}/{model}")
    candidates.extend(candidate.split("/", 1)[-1] for candidate in candidates[:])

    pricing = None
    for candidate in candidates:
        if candidate and (entry := litellm.model_cost.get(candidate)):
            pricing = entry
            break
    if not pricing:
        return None

    input_rate = pricing.get("input_cost_per_token")
    output_rate = pricing.get("output_cost_per_token")
    if input_rate is None or output_rate is None:
        return None
    cached_rate = pricing.get("cache_read_input_token_cost")
    if cached_rate is None:
        cached_rate = input_rate

    cached = min(input_tokens, cached_input_tokens)
    uncached = input_tokens - cached
    return uncached * input_rate + cached * cached_rate + output_tokens * output_rate
