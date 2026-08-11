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
# completion first to prove the harness does not accidentally discard it.
send(
    {
        "method": "thread/goal/updated",
        "params": {"goal": {"threadId": "thread-test", "status": "complete"}},
    }
)
send({"id": turn["id"], "result": {"turn": {"id": "turn-test"}}})
