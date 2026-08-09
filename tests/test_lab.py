import asyncio

import pytest

from tide import FakeExecutor, Lab, Probe, ProbeExecutor
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
        trace=lambda s: [TracePoint(t=1.0, score=0.2),
                         TracePoint(t=5.0, score=0.6, data={"snapshot": "a.json"})],
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


async def test_probe_requires_prober_and_records(tmp_path):
    async def infer(messages, model):
        return "the answer is 42"

    async def judge(output, probe):
        return {"reward": 1.0 if "42" in output else 0.0}

    lab = Lab(tmp_path / "lab", executor=FakeExecutor(),
              prober=ProbeExecutor(infer, judge))
    probe = Probe(id="q1", messages=[{"role": "user", "content": "6*7?"}],
                  rubrics=("mentions 42",))
    row = await lab.probe(probe, {"model": "m"}, tags={"phase": 3})
    assert row.kind == "probe"
    assert row.rewards["reward"] == 1.0

    bare = Lab(tmp_path / "lab2", executor=FakeExecutor())
    with pytest.raises(RuntimeError, match="no prober"):
        await bare.probe(probe)


async def test_probe_idempotent(tmp_path):
    calls = 0

    async def infer(messages, model):
        nonlocal calls
        calls += 1
        return "x"

    async def judge(output, probe):
        return {"reward": 0.0}

    lab = Lab(tmp_path / "lab", executor=FakeExecutor(),
              prober=ProbeExecutor(infer, judge))
    probe = Probe(id="q", messages=[])
    await lab.probe(probe, {"model": "m"}, tags={"v": 1})
    await lab.probe(probe, {"model": "m"}, tags={"v": 1})
    assert calls == 1
