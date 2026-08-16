"""CL-bench conversion + judge: schema-faithful fixture, mock-API grading."""

import importlib.util
import json
import sys
import threading
import tomllib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

CLBENCH = Path(__file__).parent.parent / "tasks" / "cl-bench"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"clbench_{name}", CLBENCH / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


convert = _load("convert")
judge = _load("judge")


def record(n_turns: int = 1, task_id: str = "t-1", context_id: str = "ctx-12345678"):
    """A synthetic record in the published schema (messages/rubrics/metadata)."""
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    for i in range(n_turns - 1):
        messages += [
            {"role": "user", "content": f"earlier question {i}"},
            {"role": "assistant", "content": f"reference answer {i}"},
        ]
    messages.append(
        {"role": "user", "content": "RULE BOOK: gronks beat snarfs.\nWho wins?"}
    )
    return {
        "messages": messages,
        "rubrics": ["Mentions gronks win.", "Cites the rule book."],
        "metadata": {
            "task_id": task_id,
            "context_id": context_id,
            "context_category": "Rule System Application",
            "sub_category": "Game Mechanics",
        },
    }


# ---------------------------------------------------------------- converter


def test_convert_writes_a_complete_task(tmp_path):
    task_dir = convert.convert_task(record(), tmp_path, turn=1)
    assert task_dir.name == "ctx-1234-t01"
    for piece in (
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "tests/test.sh",
        "tests/judge.py",
        "tests/rubrics.json",
        "solution/solve.sh",
    ):
        assert (task_dir / piece).exists(), piece
    config = tomllib.loads((task_dir / "task.toml").read_text())
    assert config["metadata"]["task_id"] == "t-1"
    assert config["metadata"]["turn"] == 1
    assert "OPENAI_API_KEY" in config["verifier"]["env"]
    assert json.loads((task_dir / "tests" / "rubrics.json").read_text()) == [
        "Mentions gronks win.",
        "Cites the rule book.",
    ]


def test_instruction_carries_transcript_and_answer_contract(tmp_path):
    task_dir = convert.convert_task(record(n_turns=2), tmp_path, turn=2)
    text = (task_dir / "instruction.md").read_text()
    assert "RULE BOOK: gronks beat snarfs." in text
    assert "earlier question 0" in text
    assert "Reference response" in text  # prior turns keep their reference answers
    assert "/app/answer.md" in text
    assert text.index("earlier question 0") < text.index("## Your task")


def test_convert_is_valid_stock_harbor(tmp_path):
    pytest.importorskip("harbor")
    from harbor.models.task.config import TaskConfig

    task_dir = convert.convert_task(record(), tmp_path, turn=1)
    TaskConfig.model_validate(tomllib.loads((task_dir / "task.toml").read_text()))


def test_turn_order_by_transcript_length():
    records = [record(n_turns=n, task_id=f"t-{n}") for n in (3, 1, 2)]
    ordered = convert.order_context_tasks(records)
    assert [r["metadata"]["task_id"] for r in ordered] == ["t-1", "t-2", "t-3"]


# -------------------------------------------------------------------- judge


class _Judge(BaseHTTPRequestHandler):
    verdict: dict = {}
    requests: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Judge.requests.append(body)
        reply = {"choices": [{"message": {"content": json.dumps(self.verdict)}}]}
        payload = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture()
def mock_judge(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Judge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv(
        "CLBENCH_JUDGE_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1"
    )
    monkeypatch.setenv("CLBENCH_JUDGE_API_KEY", "test-key")
    _Judge.requests = []
    yield _Judge
    server.shutdown()


def test_judge_all_rubrics_pass(mock_judge):
    mock_judge.verdict = {
        "Grading Rationale": "solid",
        "List of Requirement Satisfaction Status": ["yes", "yes"],
        "Overall Score": 1,
    }
    verdict = judge.call_judge(judge.build_prompt(["r1", "r2"], "the answer"))
    assert verdict["Overall Score"] == 1
    prompt = mock_judge.requests[0]["messages"][0]["content"]
    assert "1. r1" in prompt and "2. r2" in prompt and "the answer" in prompt


def test_judge_parse_strips_fences():
    fenced = '```json\n{"Overall Score": 0, "Grading Rationale": "x"}\n```'
    assert judge.parse_verdict(fenced)["Overall Score"] == 0
    with pytest.raises(ValueError):
        judge.parse_verdict('{"Overall Score": 7}')


def test_judge_missing_key_is_loud(monkeypatch):
    for var in ("CLBENCH_JUDGE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="no judge API key"):
        judge.call_judge("prompt")
