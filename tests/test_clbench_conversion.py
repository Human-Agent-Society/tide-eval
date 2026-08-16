"""CL-Bench conversion + scorer: real published fixtures, hand-computed IoU."""

import importlib.util
import json
import sys
import tomllib
from pathlib import Path

import pytest

CLBENCH = Path(__file__).parent.parent / "tasks" / "cl-bench"
FIXTURES = Path(__file__).parent / "fixtures" / "clbench"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"clbench_{name}", CLBENCH / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


convert = _load("convert")
scorer = _load("score_bsm")

METADATA = json.loads((FIXTURES / "mixed_grid_lifecycle_metadata.json").read_text())
SCANS = [
    json.loads(line)
    for line in (FIXTURES / "bsm_sample.jsonl").read_text().splitlines()
]


def _convert(scan, tmp_path):
    stage = convert.stage_for_scan(scan["scan_idx"], METADATA["stages"])
    return convert.convert_scan(scan, stage, tmp_path, total_scans=90)


# ---------------------------------------------------------------- converter


def test_convert_writes_a_complete_task(tmp_path):
    task_dir = _convert(SCANS[0], tmp_path)
    assert task_dir.name == "bsm-s01"
    for piece in (
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "tests/test.sh",
        "tests/score.py",
        "tests/truth.json",
        "solution/solve.sh",
    ):
        assert (task_dir / piece).exists(), piece
    config = tomllib.loads((task_dir / "task.toml").read_text())
    assert config["metadata"]["domain"] == "blind_spectrum_monitoring"
    assert config["metadata"]["scan_idx"] == 0


def test_instruction_matches_the_upstream_prompt_shape(tmp_path):
    scan = SCANS[0]
    text = (_convert(scan, tmp_path) / "instruction.md").read_text()
    assert "spectrum monitoring analyst" in text  # the system preamble
    assert f"--- Scan {scan['scan_idx'] + 1}/90 ---" in text
    for peak in scan["detected_peaks"]:
        assert peak["peak_id"] in text
    assert "Band: 0.0-168.0 MHz" in text  # stage 0 band width
    assert '"transmitters"' in text  # the exact answer schema
    assert "/app/report.json" in text


def test_stage_lookup_follows_metadata_ranges(tmp_path):
    later = SCANS[1]  # scan 40 — stage 1, a different variant
    task_dir = _convert(later, tmp_path)
    assert task_dir.name == "bsm-s41"
    config = tomllib.loads((task_dir / "task.toml").read_text())
    assert config["metadata"]["stage_idx"] == 1
    assert config["metadata"]["variant_id"] == "five_plus_four_mixed"
    with pytest.raises(ValueError, match="outside"):
        convert.stage_for_scan(999, METADATA["stages"])


def test_convert_is_valid_stock_harbor(tmp_path):
    pytest.importorskip("harbor")
    from harbor.models.task.config import TaskConfig

    task_dir = _convert(SCANS[0], tmp_path)
    TaskConfig.model_validate(tomllib.loads((task_dir / "task.toml").read_text()))


def test_truth_includes_dormant_channels(tmp_path):
    """Upstream grades against every persistent channel, active or not."""
    scan = SCANS[0]
    truth = json.loads((_convert(scan, tmp_path) / "tests" / "truth.json").read_text())
    assert len(truth["channels"]) == len(scan["ground_truth"])
    assert any(not ch["active_this_scan"] for ch in truth["channels"])


# ------------------------------------------------------------------- scorer


def test_scorer_hand_computed_iou():
    truth = {"band_width": 100.0, "channels": [{"center_freq": 50, "bandwidth": 20}]}
    perfect = [{"center_freq": 50, "bandwidth": 20}]
    assert scorer.score_report(perfect, truth)["score"] == 1.0
    # Empty report: available = whole band (100); truth available = 80.
    # IoU = 80 / 100 = 0.8.
    assert scorer.score_report([], truth)["score"] == 0.8
    # Claiming the whole band occupied: no available overlap at all.
    whole = [{"center_freq": 50, "bandwidth": 100}]
    assert scorer.score_report(whole, truth)["score"] == 0.0


def test_reference_solution_scores_exactly_one(tmp_path):
    """The oracle contract: the truth-derived report must earn IoU 1.0."""
    for scan in SCANS:
        task_dir = _convert(scan, tmp_path)
        truth = json.loads((task_dir / "tests" / "truth.json").read_text())
        solve = (task_dir / "solution" / "solve.sh").read_text()
        report = json.loads(solve.split("<<'EOF'\n")[1].split("\nEOF")[0])
        assert scorer.score_report(report["transmitters"], truth)["score"] == 1.0


def test_malformed_reports_degrade_to_empty(tmp_path):
    bad = tmp_path / "report.json"
    bad.write_text("{not json")
    transmitters, reason = scorer.load_transmitters(str(bad))
    assert transmitters == [] and "malformed" in reason
    transmitters, reason = scorer.load_transmitters(str(tmp_path / "missing.json"))
    assert transmitters == [] and "no report" in reason
