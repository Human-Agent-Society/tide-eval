import asyncio

import pytest

from tide import FakeExecutor, Lab
from tide.types import TracePoint


@pytest.fixture()
def fake():
    return FakeExecutor(score=lambda spec: {"reward": 1.0})


@pytest.fixture()
def lab(tmp_path, fake):
    return Lab(tmp_path / "lab", executor=fake)


async def test_run_stores_episode_row(lab):
    row = await lab.run("tasks/demo", {"name": "nop"}, tags={"phase": 0})
    assert row.kind == "episode"
    assert row.rewards == {"reward": 1.0}
    df = lab.df("episode")
    assert len(df) == 1
    assert df["phase"].iloc[0] == 0
    assert df["uri"].iloc[0] == "fake://tasks/demo"


async def test_idempotency_skips_and_returns_cached(lab, fake):
    r1 = await lab.run("tasks/demo", {"name": "nop"}, key="fixed")
    r2 = await lab.run("tasks/demo", {"name": "nop"}, key="fixed")
    assert r1.key == r2.key
    assert len(fake.calls) == 1  # second call never reached the executor


async def test_default_key_is_stable_and_tag_sensitive(lab, fake):
    await lab.run("tasks/demo", {"name": "nop"}, tags={"phase": 1})
    await lab.run("tasks/demo", {"name": "nop"}, tags={"phase": 1})
    await lab.run("tasks/demo", {"name": "nop"}, tags={"phase": 2})
    assert len(fake.calls) == 2  # same tags dedup, different tags run


async def test_trace_rows_recorded(tmp_path):
    fake = FakeExecutor(
        score=lambda s: {"reward": 0.8},
        trace=lambda s: [
            TracePoint(t=1.0, score=0.2),
            TracePoint(t=5.0, score=0.6, data={"snapshot": "a.json"}),
        ],
    )
    lab = Lab(tmp_path / "lab", executor=fake)
    await lab.run("tasks/ar", {"name": "x"}, key="ep")
    trace = lab.df("trace").sort_values("t")
    assert list(trace["score"]) == [0.2, 0.6]
    assert trace["snapshot"].iloc[1] == "a.json"
    assert list(trace["key"]) == ["ep#t0", "ep#t1"]


async def test_run_many_bounded_concurrency(tmp_path):
    peak = 0
    running = 0

    class SlowExec:
        async def execute(self, spec):
            nonlocal peak, running
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1
            from tide.types import EpisodeResult

            return EpisodeResult(rewards={"reward": 1.0})

    lab = Lab(tmp_path / "lab", executor=SlowExec(), concurrency=2)
    rows = await lab.run_many(
        [{"task": f"t/{i}", "agent": {"name": "nop"}} for i in range(6)]
    )
    assert len(rows) == 6
    assert peak <= 2


async def test_error_recorded_in_tags(tmp_path):
    from tide.types import EpisodeResult

    class FailingExec:
        async def execute(self, spec):
            return EpisodeResult(rewards={}, error="AgentTimeoutError: 900s")

    lab = Lab(tmp_path / "lab", executor=FailingExec())
    row = await lab.run("t/x", {"name": "nop"})
    assert "AgentTimeoutError" in row.tags["error"]


async def test_usage_is_recorded_as_episode_metrics(tmp_path):
    from tide.types import EpisodeResult

    class MeteredExec:
        async def execute(self, spec):
            return EpisodeResult(
                rewards={"reward": 0.8},
                usage={
                    "n_input_tokens": 1_000,
                    "n_cache_tokens": 600,
                    "n_output_tokens": 200,
                    "cost_usd": 0.0042,
                },
            )

    lab = Lab(tmp_path / "lab", executor=MeteredExec())
    row = await lab.run("t/x", {"name": "metered"})
    assert row.rewards == {"reward": 0.8}
    assert row.tags["n_input_tokens"] == 1_000
    assert row.tags["n_cache_tokens"] == 600
    assert row.tags["n_output_tokens"] == 200
    assert row.tags["cost_usd"] == 0.0042
