"""Fetch EdgeBench specs from HuggingFace and convert them to Harbor tasks.

    python examples/convert_edgebench.py                          # list the 51 tasks
    python examples/convert_edgebench.py ann_vector_search_qps    # convert one
    python examples/convert_edgebench.py --all                    # convert all

Converted tasks land in runs/edgebench-tasks/<task_id>/ and are stock Harbor
tasks. Run one with:

    lab = Lab("runs/edgebench")
    await lab.run("runs/edgebench-tasks/<task_id>", agent,
                  agent={"override_timeout_sec": 2 * 3600},   # the budget
                  tags={"budget": 2})

Note: EdgeBench tasks reference prebuilt work/judge images from the EdgeBench
registry; pulling them follows their docs (`sforge pull`). Requires
`pip install "tide-eval[converters]"` (PyYAML).
"""

import json
import sys
import urllib.request
from pathlib import Path

from tide.converters import convert_edgebench_task

HF = "https://huggingface.co/datasets/ByteDance-Seed/EdgeBench/resolve/main"
OUT = Path("runs/edgebench-tasks")
CACHE = Path("runs/edgebench-specs")


def fetch(name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.exists():
        urllib.request.urlretrieve(f"{HF}/{name}", path)
    return path


def list_task_ids() -> list[str]:
    with urllib.request.urlopen(
        "https://huggingface.co/api/datasets/ByteDance-Seed/EdgeBench/tree/main"
    ) as response:
        tree = json.load(response)
    return sorted(
        entry["path"].removesuffix(".json")
        for entry in tree
        if entry["path"].endswith(".json")
    )


def main() -> None:
    task_ids = list_task_ids()
    args = sys.argv[1:]
    if not args:
        print(f"{len(task_ids)} EdgeBench tasks available:")
        print("\n".join(f"  {t}" for t in task_ids))
        print("\nConvert one:  python examples/convert_edgebench.py <task_id>")
        return

    wanted = task_ids if args == ["--all"] else args
    benchmark = fetch("BENCHMARK.yaml")
    for task_id in wanted:
        if task_id not in task_ids:
            print(f"unknown task id: {task_id}")
            continue
        task_dir = convert_edgebench_task(fetch(f"{task_id}.json"), benchmark, OUT)
        print(f"converted: {task_dir}")


if __name__ == "__main__":
    main()
