"""CL-bench rubric judge — runs inside the verifier step of every converted task.

Ports the official grading protocol from Tencent-Hunyuan/CL-bench `eval.py`
verbatim, so scores stay comparable with the public leaderboard: one LLM
call grades all rubrics at once, the verdict is all-or-nothing (1 only if
every rubric passes), and a missing/empty answer scores 0 without any API
call. One deliberate deviation: where the official script counts an API
failure as score 0, this judge exits with an error instead — an unreachable
judge is an infrastructure failure, not a model failure, and recording it
as 0 would corrupt the measurement (the episode row carries the error; just
re-run it).

Configuration (set on the host; the task's verifier env forwards them):

    CLBENCH_JUDGE_API_KEY   API key (falls back to OPENAI_API_KEY)
    CLBENCH_JUDGE_MODEL     judge model, default gpt-5.1 (the paper's judge)
    CLBENCH_JUDGE_BASE_URL  OpenAI-compatible base URL, default api.openai.com/v1
"""

import json
import os
import sys
import time
import urllib.request

ANSWER_PATH = "/app/answer.md"
RUBRICS_PATH = "/tests/rubrics.json"
REWARD_PATH = "/logs/verifier/reward.txt"
VERDICT_PATH = "/logs/verifier/judge.json"

# The official CL-bench grading prompt (eval.py), unchanged.
GRADING_PROMPT = (
    "Starting now, you are a rigorous instruction-following grading teacher. Your task is to accurately grade and score student answers based on the 【Rubrics】.\n\n"
    "Grading Criteria\n"
    "This is a strict, all-or-nothing grading system. The final score is binary.\n"
    "To receive a score of 1, the student's answer must perfectly satisfy every single requirement listed in the 【Rubrics】.\n"
    "If even one requirement is not fully met, the final score will be 0.\n"
    "Grading Process\n"
    "Please strictly follow the steps below for analysis—no steps may be skipped:\n"
    "Step 1: Analyze the Standard Answer\n"
    "List all explicit requirements in the 【Rubrics】 item by item (including format, content, quantity, order, etc.).\n"
    "Identify implicit requirements in the 【Rubrics】 (e.g., language style, logical structure).\n"
    'Define specific evaluation criteria for each requirement (e.g., "must include X," "must not exceed Y").\n'
    "Step 2: Check Each Requirement Against the Student's Answer\n"
    "For every requirement in the 【Rubrics】, verify one by one whether the student's answer fully satisfies it.\n"
    "Step 3: Self-Reflection\n"
    "Before giving the final score, you must conduct the following checks:\n"
    "  Completeness Check: Whether all requirements in the standard answer have been reviewed with no omissions.\n"
    '  Strictness Check: Whether the evaluation strictly adheres to the "fully satisfied" standard without relaxing requirements due to subjective judgment.\n'
    "  Consistency Check: Whether the grading rationale aligns logically with the final score.\n"
    "  Objectivity Check: Whether judgments are based on objective facts rather than subjective speculation.\n"
    "Output Format Requirements\n"
    "【Grading Rationale】: xxx\n"
    '【List of Requirement Satisfaction Status】: [x₁, x₂, …, xᵢ, …, xₙ] (where n is the total number of requirements in the 【Rubrics】, and xᵢ indicates whether the student\'s answer meets the i-th requirement, with values "yes"/"no")\n'
    "【Overall Score】: x points (x is an integer, either 0 or 1.)\n\n"
    "Content to Be Graded\n"
    "【Rubrics】:\n{rubrics_text}\n"
    "【Student Response】:\n{model_output}\n"
    "\nPlease strictly output ONLY the following JSON format (do not output any other content):\n"
    "{{\n"
    '  "Grading Rationale": "Your detailed grading rationale",\n'
    '  "List of Requirement Satisfaction Status": ["yes", "no", ...],\n'
    '  "Overall Score": 0 or 1\n'
    "}}\n"
)


def build_prompt(rubrics: list[str], model_output: str) -> str:
    rubrics_text = "\n".join(f"{i}. {r.strip()}" for i, r in enumerate(rubrics, 1))
    return GRADING_PROMPT.format(rubrics_text=rubrics_text, model_output=model_output)


def parse_verdict(text: str) -> dict:
    """The official fence-stripping + JSON parse. Raises on garbage."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    verdict = json.loads(text.strip())
    score = int(verdict["Overall Score"])
    if score not in (0, 1):
        raise ValueError(f"judge returned non-binary score {score!r}")
    return verdict


def call_judge(prompt: str, *, retries: int = 3, delay_sec: float = 3.0) -> dict:
    base_url = os.environ.get(
        "CLBENCH_JUDGE_BASE_URL", "https://api.openai.com/v1"
    ).rstrip("/")
    model = os.environ.get("CLBENCH_JUDGE_MODEL", "gpt-5.1")
    api_key = os.environ.get("CLBENCH_JUDGE_API_KEY") or os.environ.get(
        "OPENAI_API_KEY"
    )
    if not api_key:
        raise RuntimeError(
            "no judge API key: set CLBENCH_JUDGE_API_KEY (or OPENAI_API_KEY) "
            "on the host — the task's verifier env forwards it"
        )
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}]}
    ).encode()
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = json.load(response)
            content = payload["choices"][0]["message"]["content"]
            return parse_verdict(content)
        except Exception as error:  # noqa: BLE001 — retry any API/parse hiccup
            last_error = error
            if attempt < retries - 1:
                time.sleep(delay_sec)
    raise RuntimeError(f"judge failed after {retries} attempts: {last_error}")


def _record(score: int, verdict: dict) -> None:
    with open(REWARD_PATH, "w") as f:
        f.write(str(score))
    with open(VERDICT_PATH, "w") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=1)


def main() -> int:
    os.makedirs(os.path.dirname(REWARD_PATH), exist_ok=True)
    with open(RUBRICS_PATH) as f:
        rubrics = json.load(f)

    answer = ""
    if os.path.exists(ANSWER_PATH):
        with open(ANSWER_PATH, encoding="utf-8", errors="replace") as f:
            answer = f.read()
    if not answer.strip():
        # The official protocol: no output counts as score 0. No API call.
        _record(0, {"score": 0, "rationale": f"no answer at {ANSWER_PATH}"})
        print(f"no answer at {ANSWER_PATH} -> reward 0")
        return 0

    verdict = call_judge(build_prompt(rubrics, answer))
    score = int(verdict["Overall Score"])
    _record(score, verdict)
    print(f"judge score: {score}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
