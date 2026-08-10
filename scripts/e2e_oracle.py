"""The E2E gate: run the oracle through real containers on every first-party
task and require each score to match its vectors.json expectation.

    python scripts/e2e_oracle.py                 # all tasks with vectors.json
    python scripts/e2e_oracle.py circle-packing  # a subset, by name

A task's live expectation is its pinned oracle reward (± tolerance), unless
vectors.json declares a ``live_min``/``live_max`` range (used where the live
oracle legitimately varies, e.g. compression ratios across zlib builds).
"""

import asyncio
import json
import sys
from pathlib import Path

from tide import Lab

TASKS_ROOT = Path(__file__).parent.parent / "tasks"


def discover(names: list[str]) -> list[Path]:
    tasks = sorted(
        {p.parent.parent for p in TASKS_ROOT.glob("*/*/tests/vectors.json")},
        key=lambda p: p.name,
    )
    return [t for t in tasks if t.name in names] if names else tasks


async def main(names: list[str]) -> None:
    tasks = discover(names)
    if not tasks:
        known = [t.name for t in discover([])]
        sys.exit(f"no tasks matched {names!r}; known tasks: {known}")

    lab = Lab("runs/e2e-oracle")
    failures = []
    for task_dir in tasks:
        oracle = json.loads((task_dir / "tests" / "vectors.json").read_text())["oracle"]
        row = await lab.run(str(task_dir), {"name": "oracle"}, tags={"gate": "e2e"})
        reward = row.rewards.get("reward")
        if "live_min" in oracle:
            ok = (
                reward is not None
                and oracle["live_min"] <= reward <= oracle["live_max"]
            )
            expected = f"[{oracle['live_min']}, {oracle['live_max']}]"
        else:
            tolerance = oracle.get("tolerance", 1e-9)
            ok = reward is not None and abs(reward - oracle["reward"]) <= max(
                tolerance, 1e-6
            )
            expected = f"{oracle['reward']} ± {max(tolerance, 1e-6)}"
        status = "OK " if ok else "FAIL"
        print(f"{status} {task_dir.name}: reward={reward} expected {expected}")
        if not ok:
            failures.append(task_dir.name)

    if failures:
        print(f"\nE2E FAILED for: {failures}")
        sys.exit(1)
    print("\nE2E oracle gate passed for all tasks")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
