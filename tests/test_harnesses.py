"""Offline contract tests for the issue-4 harness adapters."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from examples.harnesses.config import coral_config, openevolve_config

ROOT = Path(__file__).parent.parent
OPENEVOLVE = ROOT / "examples" / "harnesses" / "openevolve"
CODEX_DRIVER = ROOT / "examples" / "harnesses" / "codex_goal_driver.py"
FAKE_APP_SERVER = ROOT / "tests" / "fixtures" / "fake_codex_app_server.py"
CORAL_GRADER_SRC = ROOT / "examples" / "harnesses" / "coral" / "grader" / "src"


class _Judge(BaseHTTPRequestHandler):
    submissions: list[dict] = []

    def do_POST(self):
        assert self.path == "/submit"
        length = int(self.headers["Content-Length"])
        solution = json.loads(self.rfile.read(length))
        self.submissions.append(solution)
        body = json.dumps(
            {
                "score": 0.75,
                "best": 0.75,
                "remaining": 9,
                "reason": "valid",
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def _judge_server():
    _Judge.submissions = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Judge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _load_evaluator():
    spec = importlib.util.spec_from_file_location(
        "tide_openevolve_evaluator", OPENEVOLVE / "evaluator.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openevolve_evaluator_submits_candidate_to_tide(monkeypatch):
    server = _judge_server()
    try:
        monkeypatch.setenv("JUDGE_URL", f"http://127.0.0.1:{server.server_port}")
        result = _load_evaluator().evaluate(str(OPENEVOLVE / "initial_program.py"))
    finally:
        server.shutdown()
        server.server_close()

    assert result == {"score": 0.75}
    assert len(_Judge.submissions) == 1
    assert len(_Judge.submissions[0]["circles"]) == 3


def test_coral_grader_client_uses_same_judge(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(CORAL_GRADER_SRC))
    from tide_coral_grader.judge import submit_file

    solution = tmp_path / "solution.json"
    solution.write_text('{"circles": []}')
    server = _judge_server()
    try:
        result = submit_file(solution, f"http://127.0.0.1:{server.server_port}")
    finally:
        server.shutdown()
        server.server_close()

    assert result["score"] == 0.75
    assert _Judge.submissions == [{"circles": []}]


def test_codex_goal_driver_sets_persisted_goal(tmp_path):
    objective = tmp_path / "objective.txt"
    objective.write_text("improve the score")
    env = {
        **os.environ,
        "CODEX_APP_SERVER_COMMAND": f"{sys.executable} {FAKE_APP_SERVER}",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(CODEX_DRIVER),
            str(objective),
            "--model",
            "test-model",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"status": "complete"' in completed.stdout


def test_generated_configs_keep_tide_as_the_scorer():
    evolve = openevolve_config("test-model", "https://example.test/v1")
    assert evolve["llm"]["primary_model"] == "test-model"
    assert evolve["llm"]["api_base"] == "https://example.test/v1"
    assert evolve["evaluator"]["parallel_evaluations"] == 1

    coral = coral_config("pack circles", "test-model", agents=3)
    assert coral["grader"]["entrypoint"] == "tide_coral_grader.grader:Grader"
    assert coral["agents"] == {
        "count": 3,
        "runtime": "codex",
        "model": "test-model",
        "max_turns": 200,
    }
    assert "coral eval" in coral["task"]["description"]
