"""reef as tide's weight plane: training on rollouts, evaluating on versions.

tide never imports reef (and vice versa). The full contract between them is:

  1. reef sits at the model-API position: tide's agents point `api_base` at
     reef's OpenAI-compatible endpoint. Harbor never knows reef exists.
  2. reef implements the two-method WeightPlane protocol below.
  3. A thin runner (living on the reef side) reads tide's results and POSTs
     /reef/report to close the training loop.

This file is a runnable *shape* — swap the endpoint for a live `reef serve`.
"""

import asyncio

import httpx

from tide import Lab


class ReefWeightPlane:
    """WeightPlane over reef's HTTP API.

    snapshot() freezes the currently-published version and returns its ref
    (reef's version chain makes historical refs durable); serve(ref) returns
    an OpenAI-compatible base URL that pins that version — reef's per-request
    attribution guarantees a mid-battery hot-swap can't leak in.
    """

    def __init__(self, reef_url: str, scenario: str):
        self.reef_url = reef_url
        self.scenario = scenario

    def snapshot(self) -> str:
        r = httpx.get(f"{self.reef_url}/reef/versions/current",
                      params={"scenario": self.scenario})
        r.raise_for_status()
        return r.json()["version_id"]

    def serve(self, ref: str) -> str:
        # reef pins versions via header-routing on the shared endpoint; the
        # base URL encodes the pin so any OpenAI client just works.
        return f"{self.reef_url}/v1?version={ref}"


async def main():
    plane = ReefWeightPlane("http://localhost:8000", scenario="trading")
    lab = Lab("runs/reef-demo")

    # --- one lap of the loop: evaluate current weights, report, re-evaluate.
    ref = plane.snapshot()
    row = await lab.run(
        "terminal-bench/hello-world",
        # Any Harbor agent; its inference goes through reef, version-pinned.
        {"name": "terminus-2", "model_name": f"openai/{ref}",
         "kwargs": {"api_base": plane.serve(ref)}},
        tags={"version": ref, "arm": "stateful"},
    )

    # The report runner (reef-side code) closes the loop:
    httpx.post("http://localhost:8000/reef/report", json={
        "score": row.rewards.get("reward", 0.0),
        "references": [ref],
        "metadata": {"tide_key": row.key, "trial_uri": row.uri},
    })

    # Training happens inside reef; next lap snapshots the new version and
    # the results store accumulates (version, task, reward) — gain, learning
    # curves, and forgetting matrices are queries from there on.


if __name__ == "__main__":
    asyncio.run(main())
