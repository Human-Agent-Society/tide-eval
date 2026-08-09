"""Clone Continual-Learning-Bench (arXiv 2606.05661) for local use.

    python tasks/continual-learning-bench/fetch.py

Brings their harness AND their published final results (leaderboard runs of
claude/codex/icl/mem0/ace/icl_notepad). tide analyzes the results directly:

    from tide.loaders import load_clbench_results
    df = load_clbench_results("tasks/continual-learning-bench/repo/final_results/runs")

Their tasks carry a training-corpora canary; tide clones locally and never
redistributes the content.
"""

import subprocess
from pathlib import Path

DEST = Path(__file__).parent / "repo"

if __name__ == "__main__":
    if DEST.exists():
        print(f"{DEST} exists; pulling latest")
        subprocess.run(["git", "-C", str(DEST), "pull", "-q"], check=True)
    else:
        subprocess.run(
            [
                "git",
                "clone",
                "-q",
                "--depth",
                "1",
                "https://github.com/pgasawa/continual-learning-bench",
                str(DEST),
            ],
            check=True,
        )
    print(f"ready: {DEST}")
    print("analyze their published runs with tide.loaders.load_clbench_results()")
