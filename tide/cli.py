"""The tide CLI: one command from any task to a scored result.

    tide list                                           # everything runnable here
    tide run tasks/autoresearch/circle-packing --agent oracle
    tide run autoresearch --agent claude-code --model anthropic/claude-opus-5
    tide run edgebench/ann_vector_search_qps --agent codex --budget 2
    tide report                                         # summarize the results store

Targets resolve in order: an explicit task directory → every task inside a
category/benchmark folder (``autoresearch`` runs all six) → anything else is
passed to Harbor as a registry id. The CLI is a thin caller of :class:`Lab`;
everything it runs lands in the same tagged results store (``--lab``,
default ``runs/cli``), so re-running resumes and ``tide report`` is a query.

Protocols the CLI can't express (custom schedules, control arms) are plain
Python scripts over :class:`Lab` — see ``examples/``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


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
    return sorted(
        (
            p.parent
            for p in path.glob("**/task.toml")
            if not any(part.startswith(("_", ".")) for part in p.parts)
        ),
        key=lambda p: p.as_posix(),
    )


def resolve_targets(targets: list[str], tasks_root: Path | None) -> list[str]:
    """Expand CLI targets into runnable task references.

    Returns task-dir paths (as strings) and/or Harbor registry ids.
    """
    resolved: list[str] = []
    for target in targets:
        path = Path(target)
        candidates = [path]
        if tasks_root is not None:
            candidates.append(tasks_root / target)
        for candidate in candidates:
            if _is_task_dir(candidate):
                resolved.append(str(candidate))
                break
            if candidate.is_dir():
                inside = _tasks_under(candidate)
                if not inside:
                    raise SystemExit(
                        f"'{target}' is a directory but contains no task.toml — "
                        "fetch its tasks first? (see its README / `tide fetch`)"
                    )
                resolved.extend(str(t) for t in inside)
                break
        else:
            resolved.append(target)  # a Harbor registry id
    return resolved


def _build_agent(args: argparse.Namespace) -> dict:
    agent: dict = {"name": args.agent}
    if args.model:
        agent["model_name"] = args.model
    if args.budget is not None:
        agent["override_timeout_sec"] = args.budget * 3600
    for pair in args.agent_arg or []:
        key, _, value = pair.partition("=")
        try:
            agent[key] = json.loads(value)
        except json.JSONDecodeError:
            agent[key] = value
    return agent


def _parse_tags(pairs: list[str] | None) -> dict:
    tags = {}
    for pair in pairs or []:
        key, _, value = pair.partition("=")
        try:
            tags[key] = json.loads(value)
        except json.JSONDecodeError:
            tags[key] = value
    return tags


def _make_lab(args: argparse.Namespace):
    from tide import FakeExecutor, Lab, LocalExecutor

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
    print("Registry ids: tide run algotune/<task> --agent <agent> --model <m>")
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
    if args.budget is not None:
        base_tags.setdefault("budget", args.budget)

    lab = _make_lab(args)

    async def _run() -> list:
        calls = [
            {
                "task": target,
                "agent": agent,
                "tags": {**base_tags, "attempt": attempt},
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
    print(f"\nresults stored in {args.lab} — `tide report --lab {args.lab}`")
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
    tasks_root = _find_tasks_root(args.tasks_dir)
    if tasks_root is None:
        raise SystemExit("no tasks/ directory found — run from a tide checkout")
    script = tasks_root / args.benchmark / "fetch.py"
    if not script.is_file():
        available = sorted(p.parent.name for p in tasks_root.glob("*/fetch.py"))
        raise SystemExit(
            f"no fetch script for '{args.benchmark}'; available: {available}"
        )
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

    p_run = sub.add_parser("run", help="run tasks/folders/registry ids")
    p_run.add_argument("targets", nargs="+")
    p_run.add_argument(
        "--agent",
        default=None,
        help="Harbor agent name (e.g. oracle, claude-code)",
    )
    p_run.add_argument("--model", default=None, help="model name for the agent")
    p_run.add_argument(
        "--budget",
        type=float,
        default=None,
        help="hours; sets the agent timeout and a budget tag",
    )
    p_run.add_argument("--attempts", "-n", type=int, default=1)
    p_run.add_argument("--concurrent", type=int, default=4)
    p_run.add_argument("--lab", default="runs/cli", help="results directory")
    p_run.add_argument(
        "--tag", action="append", metavar="K=V", help="extra tags (repeatable)"
    )
    p_run.add_argument(
        "--agent-arg",
        action="append",
        metavar="K=V",
        help="extra AgentConfig fields (repeatable)",
    )
    p_run.add_argument(
        "--fake",
        action="store_true",
        help="use the offline fake executor (no Docker; smoke tests)",
    )
    p_run.add_argument(
        "--local",
        action="store_true",
        help="run --command on this machine against the real scorer and grader"
        " (no Docker; scores are not isolation-backed)",
    )
    p_run.add_argument(
        "--command",
        default=None,
        metavar="CMD",
        help="the shell command --local runs; it reads $JUDGE_URL and $BUDGET_SEC",
    )
    p_run.set_defaults(func=cmd_run)

    p_report = sub.add_parser("report", help="summarize a results store")
    p_report.add_argument("--lab", default="runs/cli")
    p_report.add_argument(
        "--kind", default="episode", help="episode | trace | '' for all"
    )
    p_report.set_defaults(func=cmd_report)

    p_fetch = sub.add_parser("fetch", help="fetch an external benchmark's tasks")
    p_fetch.add_argument("benchmark")
    p_fetch.add_argument("rest", nargs="*")
    p_fetch.set_defaults(func=cmd_fetch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
