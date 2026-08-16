"""Fetch CL-bench and convert it to stock Harbor tasks, pinned.

    python tasks/cl-bench/fetch.py --contexts 5      # first 5 contexts (their tasks in turn order)
    python tasks/cl-bench/fetch.py 71a2cd92          # whole contexts, by id prefix
    python tasks/cl-bench/fetch.py                   # everything: 500 contexts, 1,899 tasks

Downloads the published JSONL from the pinned HuggingFace revision
(tencent/CL-bench), then converts each record with ``convert.py``. Grading
needs an LLM judge at verify time — set ``OPENAI_API_KEY`` (or
``CLBENCH_JUDGE_API_KEY``, plus ``CLBENCH_JUDGE_MODEL`` /
``CLBENCH_JUDGE_BASE_URL`` for another provider); the default judge is the
paper's, gpt-5.1. License: evaluation/benchmarking only — no training use.

    tide stream week1 cl-bench --agent claude-code --model anthropic/claude-opus-5
"""

import argparse
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

from convert import convert_task, order_context_tasks

# The pinned HuggingFace revision of tencent/CL-bench (dataset repo commit).
REVISION = "b28a5832a09b0d96c0cf4c22e90d7c60ede25b80"
DATA_URL = (
    "https://huggingface.co/datasets/tencent/CL-bench/"
    f"resolve/{REVISION}/CL-bench.jsonl"
)
HERE = Path(__file__).parent
CACHE = HERE / ".data" / "CL-bench.jsonl"


def load_records() -> list[dict]:
    if not CACHE.exists():
        print(f"downloading CL-bench.jsonl (~90 MB, pinned {REVISION[:12]}) ...")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(DATA_URL, CACHE)
    return [json.loads(line) for line in CACHE.open(encoding="utf-8")]


def main() -> None:
    parser = argparse.ArgumentParser(description="fetch + convert CL-bench (pinned)")
    parser.add_argument(
        "contexts",
        nargs="*",
        help="context ids (prefixes work) to convert; default: all 500",
    )
    parser.add_argument(
        "--contexts",
        dest="first_n",
        type=int,
        default=None,
        metavar="N",
        help="only the first N contexts (sorted by context id)",
    )
    args = parser.parse_args()

    by_context: dict[str, list[dict]] = defaultdict(list)
    for record in load_records():
        by_context[record["metadata"]["context_id"]].append(record)

    wanted = sorted(by_context)
    if args.contexts:
        wanted = [
            ctx for ctx in wanted if any(ctx.startswith(p) for p in args.contexts)
        ]
        if not wanted:
            raise SystemExit(f"no contexts match {args.contexts}")
    if args.first_n is not None:
        wanted = wanted[: args.first_n]

    n_tasks = 0
    for ctx in wanted:
        for turn, record in enumerate(order_context_tasks(by_context[ctx]), start=1):
            convert_task(record, HERE, turn)
            n_tasks += 1

    print(f"converted {n_tasks} task(s) from {len(wanted)} context(s) -> {HERE}")
    print("license: evaluation/benchmarking only — no training use")
    print("stream them: tide stream week1 cl-bench --agent <a> --model <m>")
    print("judging needs OPENAI_API_KEY (or CLBENCH_JUDGE_* overrides) on the host")


if __name__ == "__main__":
    main()
