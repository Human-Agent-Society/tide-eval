"""The smallest complete agent harness: ~30 lines of adapter, no LLM.

Pairs with ``minimal_harness_search.py`` (the in-container random-search
loop) to show the full integration path end to end: upload your method
into the container, run it against the task's public scorer, and get back
a trusted verifier score plus your method's claimed trajectory as trace
rows. Requires Docker + ``pip install tide-eval[harbor]``.

    python examples/minimal_harness.py
"""

import asyncio
import tempfile
from pathlib import Path

from harbor.agents.base import BaseAgent

from tide import Lab, metrics

TASK = str(Path(__file__).parent.parent / "tasks" / "autoresearch" / "circle-packing")
SEARCH_SCRIPT = Path(__file__).with_name("minimal_harness_search.py")


class RandomSearchHarness(BaseAgent):
    """Uploads the search script and runs it. That is the entire adapter."""

    @staticmethod
    def name() -> str:
        return "random-search"

    def version(self) -> str | None:
        return "0.1"

    async def setup(self, environment) -> None:
        pass  # pure stdlib — nothing to install

    async def run(self, instruction, environment, context) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "search.py").write_text(SEARCH_SCRIPT.read_text())
            await environment.upload_dir(source_dir=tmp, target_dir="/opt/harness")
        await environment.exec(
            command="python /opt/harness/search.py",
            env={"BUDGET_SEC": "30"},
        )


async def main():
    lab = Lab("runs/minimal-harness")
    row = await lab.run(
        TASK,
        agent={"import_path": "minimal_harness:RandomSearchHarness"},
        tags={"harness": "random-search"},
    )
    print("trusted reward:", row.rewards)  # the verifier's verdict

    trace = lab.df("trace")
    if not trace.empty:
        curve = metrics.anytime(trace)
        print("\nclaimed progress (from the harness's own score log):")
        print(curve[["t", "score", "best_so_far"]].to_string(index=False))
        print("anytime AUC:", round(metrics.auc(curve), 4))


if __name__ == "__main__":
    asyncio.run(main())
