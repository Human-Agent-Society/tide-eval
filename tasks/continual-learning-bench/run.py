"""Run Continual-Learning-Bench through tide: one command, results in the store.

    python tasks/continual-learning-bench/fetch.py                       # once
    python tasks/continual-learning-bench/run.py exploitable_poker \\
        --system icl --schedule quick_test --lab runs/clbench

Wraps their harness (`clbench run ...` inside the fetched repo — needs their
setup: `uv sync --all-extras && clbench setup --all`, plus model keys for the
system you pick), then ingests the run's instance outcomes into a tide
results store, one row each, tagged (system, model, task, schedule,
run_index, instance_index). From there it's the usual story:

    tide report --lab runs/clbench --kind external
    df = Lab("runs/clbench").df("external")
    metrics.anytime(df, time="instance_index", score="reward", by=["system"])

Extra arguments after ``--`` pass through to `clbench run` verbatim.
"""

import argparse
import subprocess
from pathlib import Path

REPO = Path(__file__).parent / "repo"


def ingest(runs_dir: Path, lab_dir: str) -> int:
    from tide import Lab
    from tide.loaders import load_clbench_results
    from tide.types import Row

    df = load_clbench_results(runs_dir)
    if df.empty:
        print(f"no results found under {runs_dir}")
        return 0
    lab = Lab(lab_dir)
    added = 0
    for record in df.to_dict("records"):
        reward = record.pop("reward")
        key = (
            f"clbench/{record['run']}/{record['task']}/"
            f"r{record['run_index']}/i{record['instance_index']}"
        )
        if lab.store.has(key):
            continue
        lab.store.put(
            Row(
                key=key,
                kind="external",
                task=f"clbench/{record.pop('task')}",
                tags=record,
                rewards={"reward": reward},
                uri=str(runs_dir),
            )
        )
        added += 1
    print(f"ingested {added} new outcome rows into {lab_dir} (kind='external')")
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("task", help="a CLB task, e.g. exploitable_poker")
    parser.add_argument("--system", default="icl")
    parser.add_argument("--schedule", default="quick_test")
    parser.add_argument("--lab", default="runs/clbench")
    parser.add_argument(
        "--ingest-only",
        action="store_true",
        help="skip running; ingest existing results",
    )
    parser.add_argument(
        "rest", nargs="*", help="extra args passed to `clbench run` after --"
    )
    args = parser.parse_args()

    if not REPO.exists():
        raise SystemExit(
            "repo not fetched — run tasks/continual-learning-bench/fetch.py first"
        )

    if not args.ingest_only:
        cmd = [
            "uv",
            "run",
            "clbench",
            "run",
            args.task,
            "--schedule",
            args.schedule,
            "--system",
            args.system,
            *args.rest,
        ]
        print("running:", " ".join(cmd))
        result = subprocess.run(cmd, cwd=REPO)
        if result.returncode != 0:
            print("clbench run failed; not ingesting")
            return result.returncode

    # Their harness writes run manifests under results/ (live) and
    # final_results/runs/ (completed batches); ingest whichever exists.
    for candidate in (REPO / "final_results" / "runs", REPO / "results"):
        if candidate.exists():
            ingest(candidate, args.lab)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
