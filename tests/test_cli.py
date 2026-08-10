from pathlib import Path

import pytest

from tide.cli import main, resolve_targets

TASKS_ROOT = Path(__file__).parent.parent / "tasks"


def test_resolve_single_task_dir():
    target = str(TASKS_ROOT / "autoresearch" / "tsp-tour")
    assert resolve_targets([target], TASKS_ROOT) == [target]


def test_resolve_category_expands_and_skips_template():
    resolved = resolve_targets(["autoresearch"], TASKS_ROOT)
    names = [Path(r).name for r in resolved]
    assert "tsp-tour" in names and "circle-packing" in names
    assert len(names) == 6
    assert not any("_template" in r for r in resolved)


def test_resolve_registry_id_passthrough():
    assert resolve_targets(["algotune/psd_cone_projection"], TASKS_ROOT) == [
        "algotune/psd_cone_projection"
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
            "autoresearch/tsp-tour",
            "autoresearch/bin-packing",
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
    assert "autoresearch/tsp-tour" in out
    assert " 2 " in out  # count column: 2 attempts each


def test_run_is_idempotent_across_invocations(tmp_path, capsys):
    lab = str(tmp_path / "lab")
    argv = [
        "--tasks-dir",
        str(TASKS_ROOT),
        "run",
        "autoresearch/tsp-tour",
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


def test_list_and_fetch_errors(capsys):
    assert main(["--tasks-dir", str(TASKS_ROOT), "list"]) == 0
    out = capsys.readouterr().out
    assert "autoresearch/circle-packing" in out
    with pytest.raises(SystemExit, match="available"):
        main(["--tasks-dir", str(TASKS_ROOT), "fetch", "nonsense-bench"])
