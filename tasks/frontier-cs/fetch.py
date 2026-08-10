"""Generate FrontierCS Harbor tasks into this folder — both tracks.

Wraps the official Frontier-CS → Harbor adapters (MIT). One sample per
track is vendored here; this script fetches their repo and generates any
of the others. Problem ids pick the track: numeric ids are the 1.0
algorithmic track (172 open-ended competitive-programming problems),
names are the 2.0 track (20 open research problems).

    python tasks/frontier-cs/fetch.py                       # list problem ids
    python tasks/frontier-cs/fetch.py 1 17                  # algorithmic track
    python tasks/frontier-cs/fetch.py erdos_unit_distance   # 2.0 track
"""

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
REPO = "https://github.com/FrontierCS/Frontier-CS.git"
PUBLISHED_JUDGE = "yanagiorigami/frontier-cs-harbor-judge:latest"


def _generate(src: Path, module: str, pythonpath: Path, argv: list[str]) -> None:
    subprocess.run(
        [sys.executable, "-m", module, *argv],
        check=True,
        env={"PYTHONPATH": str(pythonpath), "PATH": "/usr/bin:/bin"},
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="frontiercs-") as tmp:
        src = Path(tmp) / "Frontier-CS"
        print(f"cloning {REPO} ...")
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", REPO, str(src)], check=True
        )
        algorithmic = sorted(
            (p.name for p in (src / "algorithmic" / "problems").iterdir()
             if p.is_dir()),
            key=lambda n: (len(n), n),
        )
        research = sorted(
            p.parent.name for p in (src / "2.0" / "problems").glob("*/evaluator.py")
        )
        if len(sys.argv) < 2:
            print(f"{len(algorithmic)} algorithmic-track problems (numeric ids):")
            print("  " + " ".join(algorithmic))
            print(f"\n{len(research)} 2.0-track problems:")
            print("\n".join(f"  {p}" for p in research))
            print("\nGenerate:  python tasks/frontier-cs/fetch.py <id> [...]")
            return

        wanted = sys.argv[1:]
        unknown = set(wanted) - set(algorithmic) - set(research)
        if unknown:
            raise SystemExit(f"unknown problem ids: {sorted(unknown)}")

        numeric = [w for w in wanted if w in set(algorithmic)]
        named = [w for w in wanted if w in set(research)]
        if numeric:
            _generate(
                src,
                "frontier_cs_algorithm.main",
                src / "adapters" / "frontier-cs-algorithm" / "src",
                ["--source", str(src), "--output-dir", str(HERE),
                 "--task-ids", *numeric, "--overwrite",
                 "--judge-docker-image", PUBLISHED_JUDGE],
            )
        if named:
            _generate(
                src,
                "frontier_cs_2_0.main",
                src / "adapters" / "frontier-cs-2.0" / "src",
                ["--source", str(src), "--output-dir", str(HERE),
                 "--task-ids", *named, "--overwrite"],
            )
        print(f"generated into {HERE}: {wanted}")


if __name__ == "__main__":
    main()
