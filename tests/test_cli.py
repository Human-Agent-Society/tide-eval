from pathlib import Path

import pytest

from tide.cli import main, resolve_targets

TASKS_ROOT = Path(__file__).parent.parent / "tasks"


def test_resolve_single_task_dir():
    target = str(TASKS_ROOT / "autoresearch" / "first-party" / "tsp-tour")
    assert resolve_targets([target], TASKS_ROOT) == [target]


def test_resolve_category_expands_and_skips_template():
    resolved = resolve_targets(["autoresearch/first-party"], TASKS_ROOT)
    names = [Path(r).name for r in resolved]
    assert "tsp-tour" in names and "circle-packing" in names
    assert len(names) == 6
    assert not any("_template" in r for r in resolved)


def test_resolve_registry_id_passthrough():
    assert resolve_targets(["some-benchmark/some-task"], TASKS_ROOT) == [
        "some-benchmark/some-task"
    ]


def test_resolve_empty_folder_is_loud(tmp_path):
    (tmp_path / "emptybench").mkdir()
    with pytest.raises(SystemExit, match="no task.toml"):
        resolve_targets(["emptybench"], tmp_path)


def test_run_fake_end_to_end(tmp_path, capsys):
    lab = str(tmp_path / "lab")
    code = main(
        [
            "--tasks-dir",
            str(TASKS_ROOT),
            "run",
            "autoresearch/first-party/tsp-tour",
            "autoresearch/first-party/bin-packing",
            "--agent",
            "oracle",
            "--fake",
            "--lab",
            lab,
            "-n",
            "2",
            "--tag",
            "suite=smoke",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "OK  tsp-tour" in out and "OK  bin-packing" in out

    code = main(["report", "--lab", lab])
    out = capsys.readouterr().out
    assert code == 0
    assert "first-party/tsp-tour" in out
    assert " 2 " in out  # count column: 2 attempts each


def test_run_is_idempotent_across_invocations(tmp_path, capsys):
    lab = str(tmp_path / "lab")
    argv = [
        "--tasks-dir",
        str(TASKS_ROOT),
        "run",
        "autoresearch/first-party/tsp-tour",
        "--agent",
        "oracle",
        "--fake",
        "--lab",
        lab,
    ]
    assert main(argv) == 0
    assert main(argv) == 0  # second run resumes (skips) rather than duplicating
    capsys.readouterr()
    main(["report", "--lab", lab])
    out = capsys.readouterr().out
    assert " 1 " in out  # still one row


def test_stream_fake_end_to_end(tmp_path, capsys):
    lab = str(tmp_path / "lab")
    argv = [
        "--tasks-dir",
        str(TASKS_ROOT),
        "stream",
        "week1",
        "autoresearch/first-party/tsp-tour",
        "autoresearch/first-party/bin-packing",
        "--agent",
        "oracle",
        "--fake",
        "--lab",
        lab,
    ]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "stream 'week1'" in out
    assert "[  0] tsp-tour" in out and "[  1] bin-packing" in out

    assert main(argv) == 0  # re-running a stream resumes (skips) it
    from tide import Lab

    df = Lab(lab).df("episode")
    assert len(df) == 2
    assert df["stream"].tolist() == ["week1", "week1"]
    assert sorted(df["position"].tolist()) == [0, 1]


def test_stream_shuffle_is_deterministic_and_seed_scoped(tmp_path, capsys):
    lab = str(tmp_path / "lab")
    base = [
        "--tasks-dir",
        str(TASKS_ROOT),
        "stream",
        "mix",
        "autoresearch/first-party",
        "--agent",
        "oracle",
        "--fake",
        "--lab",
        lab,
    ]
    from tide import Lab

    assert main([*base, "--shuffle", "7"]) == 0
    assert main([*base, "--shuffle", "7"]) == 0  # same seed = same stream: resumes
    df = Lab(lab).df("episode")
    assert len(df) == 6  # nothing re-ran
    assert set(df["shuffle_seed"]) == {7}

    assert main([*base, "--shuffle", "8"]) == 0  # new seed = its own stream
    df = Lab(lab).df("episode")
    assert len(df) == 12
    by_seed = {
        seed: df[df.shuffle_seed == seed].sort_values("position")["task"].tolist()
        for seed in (7, 8)
    }
    assert sorted(by_seed[7]) == sorted(by_seed[8])  # task set fixed...
    assert by_seed[7] != by_seed[8]  # ...order differs


def test_list_and_fetch_errors(capsys):
    assert main(["--tasks-dir", str(TASKS_ROOT), "list"]) == 0
    out = capsys.readouterr().out
    assert "autoresearch/first-party/circle-packing" in out
    with pytest.raises(SystemExit, match="available"):
        main(["--tasks-dir", str(TASKS_ROOT), "fetch", "nonsense-bench"])
