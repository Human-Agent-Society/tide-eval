"""The tide CLI: one command from any task to a scored result.

    tide list                                           # everything runnable here
    tide run tasks/autoresearch/first-party/circle-packing --agent oracle
    tide run autoresearch/first-party --agent claude-code --model anthropic/claude-opus-5
    tide run edgebench/ann_vector_search_qps --agent codex --budget 2
    tide stream terminal-bench --agent claude-code   # continual: carried state
    tide report                                         # summarize the results store

Targets resolve in order: an explicit task directory, then every task inside
a category or benchmark folder, then anything else passed to Harbor as a
registry id. The CLI is a thin caller of :class:`Lab`; everything it runs
lands in the same tagged results store (``--lab``, default ``runs/cli``), so
re-running resumes and ``tide report`` is a query.

Protocols the CLI cannot express (custom schedules, control arms) are plain
Python scripts over :class:`Lab`; see ``examples/``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tide import Budget, Lab


def _find_tasks_root(tasks_dir: str | None) -> Path | None:
    """Locate the tasks catalog: explicit arg → $TIDE_TASKS_DIR → ./tasks →
    the checkout the tide package itself lives in."""
    if tasks_dir:
        return Path(tasks_dir)
    env = os.environ.get("TIDE_TASKS_DIR")
    if env:
        return Path(env)
    for base in (Path.cwd(), Path(__file__).parent.parent):
        candidate = base / "tasks"
        if candidate.is_dir():
            return candidate
    return None


def _is_task_dir(path: Path) -> bool:
    return (path / "task.toml").is_file()


def _tasks_under(path: Path) -> list[Path]:
    """Every task folder inside *path*, skipping ``_``- and ``.``-prefixed
    directories such as ``_template``.

    The skip test looks only at the parts below *path*: the search root
    itself may sit anywhere, including under a dot-directory (benchmarks
    download to ``~/.cache/tide`` by default).
    """
    found = []
    for task_toml in path.glob("**/task.toml"):
        parts = task_toml.relative_to(path).parts
        if any(part.startswith(("_", ".")) for part in parts):
            continue
        found.append(task_toml.parent)
    return sorted(found, key=lambda p: p.as_posix())


def _expand(target: str, candidate: Path) -> list[str] | None:
    """A task dir resolves to itself; a folder expands to the tasks inside."""
    if _is_task_dir(candidate):
        return [str(candidate)]
    if candidate.is_dir():
        inside = _tasks_under(candidate)
        if not inside:
            raise SystemExit(
                f"'{target}' is a directory but contains no task.toml. "
                "Fetch its tasks first (see its README, or `tide fetch`)."
            )
        return [str(t) for t in inside]
    return None


def _fetch_known_benchmark(target: str) -> list[str] | None:
    """Download a known benchmark on first use (pip installs have no tasks/)."""
    from tide import fetch

    name = target.split("/", 1)[0]
    if name not in fetch.BENCHMARKS and name not in fetch.REGISTRY:
        return None
    root = fetch.benchmark(name)
    parts = target.split("/", 1)
    candidate = root / parts[1] if len(parts) == 2 else root
    return _expand(target, candidate)


def resolve_targets(targets: list[str], tasks_root: Path | None) -> list[str]:
    """Expand CLI targets into runnable task references.

    Local paths win, then the tasks catalog (at either level), then known
    benchmarks download into the cache, and anything else passes through
    to Harbor as a registry id.
    """
    resolved: list[str] = []
    for target in targets:
        candidates = [Path(target)]
        if tasks_root is not None:
            candidates.append(tasks_root / target)
            # Benchmarks live one level down (tasks/<mode>/<benchmark>), so
            # bare names like "edgebench" or "terminal-bench" resolve too.
            candidates.extend(sorted(tasks_root.glob(f"*/{target}")))
        for candidate in candidates:
            hit = _expand(target, candidate)
            if hit is not None:
                resolved.extend(hit)
                break
        else:
            hit = _fetch_known_benchmark(target)
            if hit is not None:
                resolved.extend(hit)
            else:
                resolved.append(target)  # a Harbor registry id
    return resolved


def _build_agent(args: argparse.Namespace) -> dict:
    agent: dict = {"name": args.agent}
    if args.model:
        agent["model_name"] = args.model
    for pair in args.agent_arg or []:
        key, _, value = pair.partition("=")
        try:
            agent[key] = json.loads(value)
        except json.JSONDecodeError:
            agent[key] = value
    return agent


def _build_budget(args: argparse.Namespace) -> Budget | None:
    """Assemble a Budget from the budget flags (all optional)."""
    from tide import Budget
    from tide.budget import parse_duration_hours

    budget = Budget(
        time_h=None if args.budget is None else parse_duration_hours(args.budget),
        max_submissions=args.max_evals,
        max_tokens=_parse_count(args.max_tokens),
        max_cost_usd=args.max_cost,
    )
    return None if budget.is_empty else budget


def _parse_count(value: str | None) -> int | None:
    """Accept plain ints or human suffixes: 500k, 2m, 1.5M."""
    if value is None:
        return None
    text = value.strip().lower()
    mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    if text and text[-1] in mult:
        return int(float(text[:-1]) * mult[text[-1]])
    return int(text)


def _parse_tags(pairs: list[str] | None) -> dict:
    tags = {}
    for pair in pairs or []:
        key, _, value = pair.partition("=")
        try:
            tags[key] = json.loads(value)
        except json.JSONDecodeError:
            tags[key] = value
    return tags


def _stream_name(name: str | None, targets: list[str]) -> str:
    """The stream's label: ``--name`` when given, else derived from what was
    asked for.

    The derived form is the first target's own name, plus how many more
    followed, so ``tide stream terminal-bench cl-bench`` becomes
    ``terminal-bench+1more``. It is only a label: two streams with the same
    name but different tasks or setups still keep separate state.
    """
    if name is None:
        first = targets[0].rstrip("/").split("/")[-1]
        extra = len(targets) - 1
        return f"{first}+{extra}more" if extra else first
    if not name.strip():
        raise SystemExit("--name cannot be empty")
    bad = [c for c in "/\\" if c in name]
    if bad or any(c.isspace() for c in name):
        raise SystemExit(
            f"invalid --name {name!r}: it becomes a directory name, so it "
            "cannot contain path separators or whitespace"
        )
    return name


def _enable_progress() -> None:
    """Show the tide logger's per-episode progress lines on stderr."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("tide")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def _first_build_hint(args: argparse.Namespace) -> None:
    if not getattr(args, "fake", False) and not getattr(args, "local", False):
        print(
            "note: first runs build container images and may download data; "
            "Docker caches both, so later runs start fast"
        )


def _make_lab(args: argparse.Namespace) -> Lab:
    from tide import FakeExecutor, Lab, LocalExecutor
    from tide.executors import Executor

    executor: Executor | None
    if getattr(args, "fake", False):
        executor = FakeExecutor()
    elif getattr(args, "local", False):
        executor = LocalExecutor()
    else:
        executor = None  # the default HarborExecutor (containers)
    return Lab(args.lab, executor=executor, concurrency=args.concurrent)


# ------------------------------------------------------------------ commands


def cmd_list(args: argparse.Namespace) -> int:
    tasks_root = _find_tasks_root(args.tasks_dir)
    if tasks_root is None:
        print("No tasks/ directory found here. Run from a tide checkout, or pass")
        print("--tasks-dir. Harbor registry ids always work: tide run <id> ...")
        return 1
    print(f"tasks under {tasks_root}:\n")
    for task in _tasks_under(tasks_root):
        rel = task.relative_to(tasks_root)
        print(f"  {rel}")
    print("\nRun one:      tide run <name-above> --agent oracle")
    print("Run a folder: tide run autoresearch --agent oracle")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if args.local and not args.command:
        raise SystemExit(
            "--local runs your own command: add --command '<shell command>'"
        )
    if args.command and not args.local:
        raise SystemExit("--command only works with --local")
    if args.local:
        args.agent = args.agent or "local-command"
    elif not args.agent:
        raise SystemExit("--agent is required (or use --local with --command)")

    tasks_root = _find_tasks_root(args.tasks_dir)
    targets = resolve_targets(args.targets, tasks_root)
    agent = _build_agent(args)
    if args.command:
        agent["command"] = args.command
    base_tags = _parse_tags(args.tag)
    budget = _build_budget(args)

    _enable_progress()
    _first_build_hint(args)
    lab = _make_lab(args)

    async def _run() -> list:
        calls = [
            {
                "task": target,
                "agent": agent,
                "tags": {**base_tags, "attempt": attempt},
                "budget": budget,
            }
            for target in targets
            for attempt in range(args.attempts)
        ]
        return await lab.run_many(calls)

    print(
        f"running {len(targets)} task(s) x {args.attempts} attempt(s) "
        f"as agent '{args.agent}' -> {args.lab}"
    )
    rows = asyncio.run(_run())

    failures = 0
    for row in rows:
        reward = row.rewards.get("reward")
        error = row.tags.get("error")
        marker = "OK " if reward is not None and not error else "ERR"
        if marker == "ERR":
            failures += 1
        name = row.task.rstrip("/").split("/")[-1]
        print(f"  {marker} {name}: {row.rewards or error}")
    print(f"\nresults stored in {args.lab}: `tide report --lab {args.lab}`")
    return 1 if failures else 0


def cmd_stream(args: argparse.Namespace) -> int:
    if args.local and not args.command:
        raise SystemExit(
            "--local runs your own command: add --command '<shell command>'"
        )
    if args.command and not args.local:
        raise SystemExit("--command only works with --local")
    if args.local:
        args.agent = args.agent or "local-command"
    elif not args.agent:
        raise SystemExit("--agent is required (or use --local with --command)")

    tasks_root = _find_tasks_root(args.tasks_dir)
    # Derive the label from what was typed, not from the expansion, so
    # `tide stream terminal-bench` is named for the benchmark.
    name = _stream_name(args.name, args.targets)
    targets = resolve_targets(args.targets, tasks_root)
    agent = _build_agent(args)
    if args.command:
        agent["command"] = args.command
    tags = _parse_tags(args.tag)
    budget = _build_budget(args)
    if args.shuffle is not None:
        # The seed becomes a tag, so each seed is its own stream with its
        # own state, keys, and resume.
        import random

        random.Random(args.shuffle).shuffle(targets)
        tags = {**tags, "shuffle_seed": args.shuffle}

    from tide import Stream

    _enable_progress()
    _first_build_hint(args)
    stream = Stream(name, targets)
    lab = _make_lab(args)
    print(
        f"stream '{name}': {len(targets)} task(s) in order, "
        f"agent '{args.agent}', state carried between episodes -> {args.lab}"
    )
    print(f"state: {stream.state_root(lab, agent, tags=tags, budget=budget)}")
    rows = asyncio.run(stream.run(lab, agent, tags=tags, budget=budget))

    failures = 0
    for row in rows:
        reward = row.rewards.get("reward")
        error = row.tags.get("error")
        marker = "OK " if reward is not None and not error else "ERR"
        if marker == "ERR":
            failures += 1
        name = row.task.rstrip("/").split("/")[-1]
        print(
            f"  {marker} [{row.tags.get('position'):>3}] {name}: {row.rewards or error}"
        )
    print(f"\nresults stored in {args.lab}: `tide report --lab {args.lab}`")
    return 1 if failures else 0


def cmd_report(args: argparse.Namespace) -> int:
    from tide import Lab

    lab = Lab(args.lab)
    df = lab.df(args.kind or None)
    if df.empty:
        print(f"no rows in {args.lab}")
        return 1
    if "reward" in df.columns:
        df = df.assign(
            task=df["task"].map(lambda t: "/".join(t.rstrip("/").split("/")[-2:]))
        )
        summary = (
            df.groupby("task")["reward"].agg(["count", "mean", "max"]).sort_index()
        )
        print(summary.to_string())
    else:
        print(df.to_string(max_rows=50))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    # In a checkout, a benchmark's own fetch.py regenerates from upstream.
    tasks_root = _find_tasks_root(args.tasks_dir)
    script = None
    if tasks_root is not None:
        matches = sorted(tasks_root.glob(f"*/{args.benchmark}/fetch.py")) + [
            tasks_root / args.benchmark / "fetch.py"
        ]
        script = next((m for m in matches if m.is_file()), None)
    if script is None:
        from tide import fetch

        if args.benchmark in fetch.BENCHMARKS or args.benchmark in fetch.REGISTRY:
            dest = fetch.benchmark(args.benchmark)
            print(f"downloaded to {dest}")
            print(f"run with: tide run {args.benchmark}/<task> --agent <a>")
            return 0
        known = fetch.known_benchmarks()
        raise SystemExit(f"unknown benchmark '{args.benchmark}'; known: {known}")
    import subprocess

    return subprocess.run(
        [sys.executable, str(script), *args.rest], check=False
    ).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tide", description="autoresearch evaluation on the Harbor task standard"
    )
    from tide import __version__

    parser.add_argument("--version", action="version", version=f"tide {__version__}")
    parser.add_argument("--tasks-dir", default=None, help="tasks catalog root")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list runnable tasks")
    p_list.set_defaults(func=cmd_list)

    def add_shared_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--agent",
            default=None,
            help="Harbor agent name (e.g. oracle, claude-code)",
        )
        p.add_argument("--model", default=None, help="model name for the agent")
        p.add_argument(
            "--budget",
            default=None,
            metavar="DURATION",
            help="time budget: 2h / 30m / 90s (a bare number = hours). "
            "HARD: sets the container timeout",
        )
        p.add_argument(
            "--max-evals",
            type=int,
            default=None,
            metavar="N",
            help="submission/eval budget (agent signal; judge caps at the "
            "task's own limit)",
        )
        p.add_argument(
            "--max-tokens",
            default=None,
            metavar="N",
            help="token budget, e.g. 500k or 2m (soft: signalled to the agent, "
            "actuals recorded)",
        )
        p.add_argument(
            "--max-cost",
            type=float,
            default=None,
            metavar="USD",
            help="cost budget in USD (soft: signalled to the agent, actuals recorded)",
        )
        p.add_argument("--lab", default="runs/cli", help="results directory")
        p.add_argument(
            "--tag", action="append", metavar="K=V", help="extra tags (repeatable)"
        )
        p.add_argument(
            "--agent-arg",
            action="append",
            metavar="K=V",
            help="extra AgentConfig fields (repeatable)",
        )
        p.add_argument(
            "--fake",
            action="store_true",
            help="use the offline fake executor (no Docker; smoke tests)",
        )
        p.add_argument(
            "--local",
            action="store_true",
            help="run --command on this machine against the real scorer and grader"
            " (no Docker; scores are not isolation-backed)",
        )
        p.add_argument(
            "--command",
            default=None,
            metavar="CMD",
            help="the shell command --local runs; it reads $JUDGE_URL and $BUDGET_SEC",
        )

    p_run = sub.add_parser("run", help="run tasks/folders/registry ids")
    p_run.add_argument("targets", nargs="+")
    add_shared_flags(p_run)
    p_run.add_argument("--attempts", "-n", type=int, default=1)
    p_run.add_argument("--concurrent", type=int, default=4)
    p_run.set_defaults(func=cmd_run)

    p_stream = sub.add_parser(
        "stream",
        help="run tasks as one continual-learning stream (carried agent state)",
    )
    p_stream.add_argument("targets", nargs="+")
    add_shared_flags(p_stream)
    p_stream.add_argument(
        "--name",
        default=None,
        metavar="NAME",
        help="label for this stream, recorded as the `stream` tag and used as "
        "its state directory (default: derived from the targets). Pass a new "
        "name to start the same tasks over with empty memory",
    )
    p_stream.add_argument(
        "--shuffle",
        type=int,
        default=None,
        metavar="SEED",
        help="deterministically shuffle the task order with this seed "
        "(interleaved streams; the seed is recorded as a shuffle_seed tag)",
    )
    p_stream.set_defaults(func=cmd_stream, concurrent=1)

    p_report = sub.add_parser("report", help="summarize a results store")
    p_report.add_argument("--lab", default="runs/cli")
    p_report.add_argument(
        "--kind", default="episode", help="episode | trace | '' for all"
    )
    p_report.set_defaults(func=cmd_report)

    p_fetch = sub.add_parser("fetch", help="fetch an external benchmark's tasks")
    p_fetch.add_argument("benchmark")
    # REMAINDER so flags like `--limit 10` pass through to the fetch script.
    p_fetch.add_argument("rest", nargs=argparse.REMAINDER)
    p_fetch.set_defaults(func=cmd_fetch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
