"""Drive Codex Goal mode through the app-server JSON-RPC protocol.

The app-server goal methods manage the same persistent state as interactive
``/goal``. Keeping this client separate makes that state machine testable
without making a real model call.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, TextIO


class AppServer:
    def __init__(self, command: list[str]) -> None:
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.stdin: TextIO = self.process.stdin
        self.stdout: TextIO = self.process.stdout
        self.pending: list[dict[str, Any]] = []

    def send(self, message: dict[str, Any]) -> None:
        self.stdin.write(json.dumps(message) + "\n")
        self.stdin.flush()

    def read(self) -> dict[str, Any]:
        line = self.stdout.readline()
        if not line:
            code = self.process.poll()
            raise RuntimeError(f"Codex app-server closed unexpectedly (exit {code})")
        print(line, end="", flush=True)
        return json.loads(line)

    def response(self, request_id: int) -> dict[str, Any]:
        while True:
            message = self.read()
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"app-server request failed: {message['error']}")
                return message["result"]
            self.pending.append(message)

    def event(self) -> dict[str, Any]:
        if self.pending:
            return self.pending.pop(0)
        return self.read()

    def close(self) -> None:
        self.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)


def _normalize_usage(value: dict[str, Any]) -> dict[str, int]:
    return {
        "input_tokens": int(value.get("inputTokens", 0)),
        "cached_input_tokens": int(value.get("cachedInputTokens", 0)),
        "output_tokens": int(value.get("outputTokens", 0)),
    }


def run_goal(
    objective: str,
    model: str,
    token_budget: int | None = None,
    usage_file: Path | None = None,
) -> dict[str, Any]:
    command_text = os.environ.get(
        "CODEX_APP_SERVER_COMMAND", "codex app-server --stdio"
    )
    server = AppServer(shlex.split(command_text))
    usage: dict[str, Any] = {}
    try:
        server.send(
            {
                "method": "initialize",
                "id": 0,
                "params": {
                    "clientInfo": {
                        "name": "tide_eval",
                        "title": "Tide evaluation harness",
                        "version": "0.2.0",
                    }
                },
            }
        )
        server.response(0)
        server.send({"method": "initialized", "params": {}})

        server.send(
            {
                "method": "thread/start",
                "id": 1,
                "params": {
                    "model": model,
                    "cwd": os.getcwd(),
                    "approvalPolicy": "never",
                    "sandbox": "dangerFullAccess",
                    "serviceName": "tide-eval",
                },
            }
        )
        thread_id = server.response(1)["thread"]["id"]

        goal: dict[str, Any] = {
            "threadId": thread_id,
            "objective": objective,
            "status": "active",
        }
        if token_budget is not None:
            goal["tokenBudget"] = token_budget
        server.send({"method": "thread/goal/set", "id": 2, "params": goal})
        server.response(2)

        server.send(
            {
                "method": "turn/start",
                "id": 3,
                "params": {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": objective}],
                },
            }
        )
        server.response(3)

        while True:
            message = server.event()
            if message.get("method") == "thread/tokenUsage/updated":
                total = message.get("params", {}).get("tokenUsage", {}).get("total", {})
                if isinstance(total, dict):
                    usage = {"model": model, **_normalize_usage(total)}
                    if usage_file:
                        usage_file.parent.mkdir(parents=True, exist_ok=True)
                        usage_file.write_text(
                            json.dumps(usage, separators=(",", ":")) + "\n"
                        )
                continue
            if message.get("method") != "thread/goal/updated":
                continue
            status = message.get("params", {}).get("goal", {}).get("status")
            if status in {"complete", "blocked"}:
                if status == "blocked":
                    raise RuntimeError("Codex goal ended blocked")
                return usage
    finally:
        server.close()
