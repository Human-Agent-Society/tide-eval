"""Download Tencent CL-bench / CL-bench Life JSONL into this folder.

The data is licensed by Tencent (see their HuggingFace page) and is not
redistributed in this repo — this script fetches it for local use.

    python tasks/clbench-tencent/fetch.py            # CL-bench (1,899 records, ~90 MB)
    python tasks/clbench-tencent/fetch.py life       # CL-bench Life (405 records)

Then load probes and build the arms:

    from tide.loaders import load_rubric_probes, strip_context, reveal_phases
    probes = load_rubric_probes("tasks/clbench-tencent/CL-bench.jsonl", limit=50)
"""

import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
SETS = {
    "main": ("tencent/CL-bench", "CL-bench.jsonl"),
    "life": ("tencent/CL-bench-Life", "CL-bench-Life.jsonl"),
}


def main() -> None:
    which = "life" if "life" in sys.argv[1:] else "main"
    repo, filename = SETS[which]
    url = f"https://huggingface.co/datasets/{repo}/resolve/main/{filename}"
    dest = HERE / filename
    print(f"downloading {url}\n -> {dest}")
    urllib.request.urlretrieve(url, dest)
    print(f"done ({dest.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
