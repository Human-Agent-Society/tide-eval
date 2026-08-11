"""Deterministic app-server double for the Codex Goal harness test."""

import json
import sys


def read() -> dict:
    return json.loads(sys.stdin.readline())


def send(value: dict) -> None:
    print(json.dumps(value), flush=True)


initialize = read()
assert initialize["method"] == "initialize"
send({"id": initialize["id"], "result": {"userAgent": "fake"}})
assert read()["method"] == "initialized"

start = read()
assert start["method"] == "thread/start"
send({"id": start["id"], "result": {"thread": {"id": "thread-test"}}})

goal = read()
assert goal["method"] == "thread/goal/set"
assert goal["params"]["objective"] == "improve the score"
send({"id": goal["id"], "result": {"goal": goal["params"]}})

turn = read()
assert turn["method"] == "turn/start"
# Real app-server notifications can interleave with request responses. Emit
# usage and completion before the response to prove the harness buffers both.
send(
    {
        "method": "thread/tokenUsage/updated",
        "params": {
            "threadId": "thread-test",
            "turnId": "turn-test",
            "tokenUsage": {
                "total": {
                    "inputTokens": 120,
                    "cachedInputTokens": 80,
                    "outputTokens": 30,
                    "reasoningOutputTokens": 10,
                    "totalTokens": 150,
                }
            },
        },
    }
)
send(
    {
        "method": "thread/goal/updated",
        "params": {"goal": {"threadId": "thread-test", "status": "complete"}},
    }
)
send({"id": turn["id"], "result": {"turn": {"id": "turn-test"}}})
