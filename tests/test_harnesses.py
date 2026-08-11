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
from types import SimpleNamespace

import pytest

from examples.harnesses.common import populate_usage_context
from examples.harnesses.coral.config import coral_config
from examples.harnesses.openevolve.config import openevolve_config

ROOT = Path(__file__).parent.parent
OPENEVOLVE = ROOT / "examples" / "harnesses" / "openevolve"
CODEX_PACKAGE = ROOT / "examples" / "harnesses" / "codex"
CODEX_SRC = CODEX_PACKAGE / "src"
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
    usage = tmp_path / "usage.jsonl"
    objective.write_text("improve the score")
    env = {
        **os.environ,
        "CODEX_APP_SERVER_COMMAND": f"{sys.executable} {FAKE_APP_SERVER}",
        "PYTHONPATH": str(CODEX_SRC),
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tide_codex_goal",
            str(objective),
            "--model",
            "test-model",
            "--usage-file",
            str(usage),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"status": "complete"' in completed.stdout
    assert json.loads(usage.read_text()) == {
        "model": "test-model",
        "input_tokens": 120,
        "cached_input_tokens": 80,
        "output_tokens": 30,
    }


def test_codex_goal_package_exports_driver(monkeypatch):
    monkeypatch.syspath_prepend(str(CODEX_SRC))
    from tide_codex_goal import AppServer, run_goal

    assert AppServer.__module__ == "tide_codex_goal.app_server"
    assert callable(run_goal)


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


def test_coral_usage_aggregates_every_codex_turn(tmp_path):
    from examples.harnesses.coral.usage import usage_records

    logs = tmp_path / "results" / "run" / ".coral" / "public" / "logs"
    logs.mkdir(parents=True)
    (logs / "agent-1.0.log").write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"one"}',
                '{"type":"turn.completed","usage":{"input_tokens":100,'
                '"cached_input_tokens":60,"output_tokens":20}}',
            ]
        )
    )
    (logs / "agent-2.0.log").write_text(
        '{"type":"turn.completed","usage":{"input_tokens":200,'
        '"cached_input_tokens":100,"output_tokens":40}}\n'
    )

    assert list(usage_records(tmp_path, "test-model")) == [
        {
            "model": "test-model",
            "input_tokens": 100,
            "cached_input_tokens": 60,
            "output_tokens": 20,
        },
        {
            "model": "test-model",
            "input_tokens": 200,
            "cached_input_tokens": 100,
            "output_tokens": 40,
        },
    ]


def test_usage_populates_harbor_context_and_cost():
    pytest.importorskip("litellm")
    context = SimpleNamespace(
        n_input_tokens=None,
        n_cache_tokens=None,
        n_output_tokens=None,
        cost_usd=None,
        metadata=None,
    )
    populate_usage_context(
        context,
        [
            {
                "model": "gpt-5-mini",
                "input_tokens": 1_000,
                "cached_input_tokens": 600,
                "output_tokens": 200,
            }
        ],
        "openai/gpt-5-mini",
    )

    assert context.n_input_tokens == 1_000
    assert context.n_cache_tokens == 600
    assert context.n_output_tokens == 200
    assert context.cost_usd > 0
    assert context.metadata["cost_usd_is_estimate"] is True


def test_openevolve_usage_patch_records_sdk_usage(tmp_path, monkeypatch):
    pytest.importorskip("openevolve")
    usage_path = tmp_path / "usage.jsonl"
    monkeypatch.setenv("TIDE_USAGE_FILE", str(usage_path))
    spec = importlib.util.spec_from_file_location(
        "tide_openevolve_usage_patch", OPENEVOLVE / "sitecustomize.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module._record_usage(
        SimpleNamespace(
            model="gpt-5-mini",
            usage=SimpleNamespace(
                prompt_tokens=90,
                prompt_tokens_details=SimpleNamespace(cached_tokens=50),
                completion_tokens=20,
            ),
        ),
        "fallback-model",
    )
    assert json.loads(usage_path.read_text()) == {
        "model": "gpt-5-mini",
        "input_tokens": 90,
        "cached_input_tokens": 50,
        "output_tokens": 20,
    }
