"""The probe executor: direct inference + rubric judging, no container.

Probes are how streams measure capability densely: a probe is one prompt, one
model response, and a judge that checks the response against rubrics. It costs
an API call, not a container — so per-phase capability tracking (forgetting
matrices, internalization curves) stays affordable.

The executor is deliberately pluggable: ``infer`` and ``judge`` are async
callables, so tests inject fakes and production can use any client. A default
OpenAI-compatible pair is provided via :func:`openai_infer` /
:func:`openai_rubric_judge` (requires the ``probe`` extra).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from tide.types import Rewards

Messages = list[dict[str, str]]
InferFn = Callable[[Messages, dict[str, Any]], Awaitable[str]]
JudgeFn = Callable[[str, "Probe"], Awaitable[Rewards]]


@dataclass(frozen=True)
class Probe:
    """One probe: a prompt, rubrics to judge the answer against, and an id.

    ``messages`` follows the OpenAI chat format. ``rubrics`` are natural-
    language criteria; the judge returns per-rubric verdicts and an aggregate
    ``reward`` (all-pass = 1.0, else fraction passed — override the judge for
    different aggregation).
    """

    id: str
    messages: Messages
    rubrics: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)


class ProbeExecutor:
    def __init__(self, infer: InferFn, judge: JudgeFn):
        self._infer = infer
        self._judge = judge

    async def execute(self, probe: Probe, model: dict[str, Any]) -> Rewards:
        output = await self._infer(probe.messages, model)
        return await self._judge(output, probe)


# ---------------------------------------------------------------------------
# Default OpenAI-compatible implementations (optional `probe` extra).
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = """You are grading a model's answer against a rubric checklist.
For each rubric, answer PASS or FAIL on its own line, as `<n>. PASS` or
`<n>. FAIL`, with no other text.

[Answer]
{answer}

[Rubrics]
{rubrics}
"""


def openai_infer(client: Any) -> InferFn:
    """Build an ``infer`` from an ``openai.AsyncOpenAI``-compatible client.

    ``model`` dict keys pass through to ``chat.completions.create``
    (``model`` is required; ``base_url`` belongs on the client).
    """

    async def infer(messages: Messages, model: dict[str, Any]) -> str:
        response = await client.chat.completions.create(
            messages=messages, **model
        )
        return response.choices[0].message.content or ""

    return infer


def openai_rubric_judge(client: Any, judge_model: str) -> JudgeFn:
    """All-rubrics judge in the CL-bench style: reward 1.0 only if every
    rubric passes; ``fraction_passed`` is also reported."""

    async def judge(output: str, probe: Probe) -> Rewards:
        if not probe.rubrics:
            raise ValueError(f"Probe {probe.id!r} has no rubrics to judge against")
        rubric_text = "\n".join(
            f"{i}. {r}" for i, r in enumerate(probe.rubrics, start=1)
        )
        response = await client.chat.completions.create(
            model=judge_model,
            messages=[
                {
                    "role": "user",
                    "content": _JUDGE_PROMPT.format(
                        answer=output, rubrics=rubric_text
                    ),
                }
            ],
        )
        text = response.choices[0].message.content or ""
        verdicts = _parse_verdicts(text, len(probe.rubrics))
        passed = sum(verdicts)
        return {
            "reward": 1.0 if passed == len(probe.rubrics) else 0.0,
            "fraction_passed": passed / len(probe.rubrics),
        }

    return judge


def _parse_verdicts(text: str, n: int) -> list[bool]:
    """Parse `<n>. PASS/FAIL` lines; missing or malformed lines count FAIL
    (conservative: an unparseable judgment never awards credit)."""
    verdicts = [False] * n
    for line in text.splitlines():
        parts = line.strip().split(".", maxsplit=1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        idx = int(parts[0]) - 1
        if 0 <= idx < n:
            verdicts[idx] = parts[1].strip().upper().startswith("PASS")
    return verdicts
