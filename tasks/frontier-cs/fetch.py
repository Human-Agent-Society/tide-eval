"""Generate FrontierCS 2.0 Harbor tasks into this folder.

Wraps the official Frontier-CS 2.0 → Harbor adapter (MIT). One generated
task (frontier-cs-2-0-erdos-demo) is vendored here as a working sample; this
script fetches their repo and generates any of the others.

    python tasks/frontier-cs/fetch.py                       # list problem ids
    python tasks/frontier-cs/fetch.py erdos_unit_distance   # generate one
"""

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
REPO = "https://github.com/FrontierCS/Frontier-CS.git"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="frontiercs-") as tmp:
        src = Path(tmp) / "Frontier-CS"
        print(f"cloning {REPO} ...")
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", REPO, str(src)], check=True
        )
        problems = sorted(
            p.parent.name for p in (src / "2.0" / "problems").glob("*/evaluator.py")
        )
        if len(sys.argv) < 2:
            print(f"{len(problems)} FrontierCS 2.0 problems:")
            print("\n".join(f"  {p}" for p in problems))
            print("\nGenerate one:  python tasks/frontier-cs/fetch.py <problem_id>")
            return

        wanted = sys.argv[1:]
        unknown = set(wanted) - set(problems)
        if unknown:
            raise SystemExit(f"unknown problem ids: {sorted(unknown)}")
        subprocess.run(
            [
                sys.executable, "-m", "frontier_cs_2_0.main",
                "--source", str(src),
                "--output-dir", str(HERE),
                "--task-ids", *wanted,
                "--overwrite",
            ],
            check=True,
            env={
                "PYTHONPATH": str(src / "adapters" / "frontier-cs-2.0" / "src"),
                "PATH": "/usr/bin:/bin",
            },
        )
        print(f"generated into {HERE}: {wanted}")


if __name__ == "__main__":
    main()
