"""Fetch CL-Bench's blind-spectrum-monitoring corpus and convert it, pinned.

    python tasks/cl-bench/fetch.py               # all 90 scans
    python tasks/cl-bench/fetch.py --limit 10    # the first 10 — a starter stream

Downloads the published corpus and its metadata from the pinned commit of
pgasawa/continual-learning-bench (Apache-2.0), verifies the corpus against
the sha256 the metadata itself declares, and converts every scan with
``convert.py``. Scoring is the upstream IoU metric — deterministic and
offline, no LLM judge, no API key. Then:

    tide stream my-stream cl-bench --agent claude-code --model anthropic/claude-opus-5
"""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from convert import convert_scan, stage_for_scan

# The pinned upstream commit (main at conversion time).
COMMIT = "5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26"
RAW = (
    "https://raw.githubusercontent.com/pgasawa/continual-learning-bench/"
    f"{COMMIT}/data/blind_spectrum_monitoring"
)
HERE = Path(__file__).parent
CACHE = HERE / ".data"


def _download(name: str) -> Path:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"{RAW}/{name}", path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="fetch + convert CL-Bench blind spectrum monitoring (pinned)"
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N", help="only the first N scans"
    )
    args = parser.parse_args()

    metadata = json.loads(_download("mixed_grid_lifecycle_metadata.json").read_text())
    corpus_path = _download("mixed_grid_lifecycle.jsonl")
    digest = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    if digest != metadata["jsonl_sha256"]:
        raise SystemExit(
            f"corpus integrity check failed: sha256 {digest[:16]}... does not "
            f"match the metadata's {metadata['jsonl_sha256'][:16]}..."
        )

    scans = [json.loads(line) for line in corpus_path.open(encoding="utf-8")]
    scans.sort(key=lambda s: s["scan_idx"])
    if args.limit is not None:
        scans = scans[: args.limit]

    total = metadata["total_scans"]
    for scan in scans:
        stage = stage_for_scan(scan["scan_idx"], metadata["stages"])
        convert_scan(scan, stage, HERE, total_scans=total)

    print(f"converted {len(scans)}/{total} blind-spectrum scans -> {HERE}")
    print("stream them: tide stream my-stream cl-bench --agent <a> --model <m>")


if __name__ == "__main__":
    main()
