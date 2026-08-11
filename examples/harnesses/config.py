"""Pure configuration builders for the example harnesses."""

from __future__ import annotations

from typing import Any


def openevolve_config(model: str, api_base: str | None = None) -> dict[str, Any]:
    """Return a small, reproducible OpenEvolve configuration."""
    llm: dict[str, Any] = {
        "primary_model": model,
        "primary_model_weight": 1.0,
        "temperature": 0.7,
        "max_tokens": 16_000,
        "timeout": 120,
    }
    if api_base:
        llm["api_base"] = api_base
    return {
        "max_iterations": 100,
        "checkpoint_interval": 10,
        "llm": llm,
        "prompt": {
            "system_message": (
                "Improve the program's circle packing. Preserve its JSON output "
                "contract; the evaluator returns the Tide judge's score."
            )
        },
        "database": {
            "population_size": 30,
            "archive_size": 15,
            "num_islands": 2,
            "elite_selection_ratio": 0.2,
            "exploitation_ratio": 0.7,
        },
        "evaluator": {"timeout": 60, "parallel_evaluations": 1},
        "diff_based_evolution": True,
        "max_code_length": 20_000,
    }


def coral_config(
    instruction: str,
    model: str,
    *,
    agents: int = 2,
) -> dict[str, Any]:
    """Return a CORAL task whose only grader is the Tide judge."""
    description = f"""{instruction}

Work on solution.json. It must contain exactly the JSON solution described above.
Run `coral eval` whenever a candidate is worth spending one Tide submission on.
The returned score and feedback come directly from the Tide judge. Keep the best
candidate in solution.json and commit useful improvements so the other agents can
build on them.
"""
    return {
        "task": {
            "name": "Tide benchmark",
            "description": description,
            "tips": (
                "Submissions are limited. Use local checks for cheap filtering and "
                "reserve `coral eval` for promising candidates."
            ),
        },
        "grader": {
            "entrypoint": "tide_coral_grader.grader:Grader",
            "setup": ["uv pip install -e ./grader"],
            "timeout": 60,
            "direction": "maximize",
            "args": {"solution_file": "solution.json"},
        },
        "agents": {
            "count": agents,
            "runtime": "codex",
            "model": model,
            "max_turns": 200,
        },
        "workspace": {
            "results_dir": "./results",
            "repo_path": "./seed",
        },
        "run": {"verbose": False, "ui": False, "session": "local"},
    }
