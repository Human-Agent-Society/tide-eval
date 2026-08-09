"""Harbor-dependent tests: skipped cleanly when harbor isn't installed.

These pin the *mapping* between tide and Harbor (config assembly, task
validation) without running containers. Full end-to-end runs live in
examples/ and require Docker.
"""

import pytest

harbor = pytest.importorskip("harbor")


def test_agent_dict_maps_onto_agent_config():
    from harbor.models.trial.config import AgentConfig

    cfg = AgentConfig.model_validate(
        {"name": "claude-code", "model_name": "anthropic/claude-opus-5"}
    )
    assert cfg.name == "claude-code"


def test_trial_config_assembly_matches_executor():
    from harbor.models.trial.config import TaskConfig, TrialConfig

    config = TrialConfig.model_validate(
        {
            "task": TaskConfig.model_validate({"name": "org/some-task"}).model_dump(),
            "trials_dir": "trials",
            "agent": {"name": "nop"},
            "verifier": {"disable": True},
        }
    )
    assert config.agent.name == "nop"
    assert config.verifier.disable is True


def test_exemplar_task_is_valid_stock_harbor(request):
    """The shipped autoresearch exemplar must parse under Harbor's TaskConfig
    schema — the 'tasks stay 100% stock harbor' promise, enforced."""
    import tomllib
    from pathlib import Path

    from harbor.models.task.config import TaskConfig

    task_dir = (
        Path(request.config.rootpath) / "tasks" / "autoresearch" / "circle-packing"
    )
    raw = tomllib.loads((task_dir / "task.toml").read_text())
    cfg = TaskConfig.model_validate(raw)
    assert cfg.verifier is not None
    assert (task_dir / "instruction.md").exists()
    assert (task_dir / "environment" / "Dockerfile").exists()
    assert (task_dir / "tests" / "test.sh").exists()
    assert (task_dir / "solution" / "solve.sh").exists()
