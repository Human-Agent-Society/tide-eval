# FrontierCS

Open-ended CS problems from
[FrontierCS/Frontier-CS](https://github.com/FrontierCS/Frontier-CS) (MIT):
the optimal solution is unknown, but quality is objectively scored —
continuous partial credit, expert-curated
([paper](https://arxiv.org/abs/2512.15699)). Two tracks are supported,
both generated verbatim by their official Harbor adapters:

- **1.0 algorithmic track** — 172 open-ended competitive-programming
  problems (many NP-hard variants), C++17, per-problem testlib checkers.
  Their adapter is judge-native: an HTTP judge sidecar grades submissions
  during the session (`bash /app/submit.sh`), and the final score is the
  best of the last solution and the best graded submission. Sample
  vendored: `frontier-cs-algorithm-1/` (Treasure Packing).
- **2.0 track** — 20 open research problems (Erdős constructions,
  BBOPlace, GPU kernels …) with in-task `submit.sh` self-scoring; all 20
  committed, including four GPU kernel tasks whose judge sidecars
  demonstrate the compose-overlay wiring from
  [docs/components/tasks.md](../../docs/components/tasks.md).

Run any task:

```bash
tide run frontier-cs/frontier-cs-algorithm-1 --agent claude-code --model anthropic/claude-opus-5
tide run frontier-cs/frontier-cs-2-0-erdos-demo --agent oracle
```

Generate more (ids pick the track — numeric = algorithmic, named = 2.0):

```bash
python tasks/frontier-cs/fetch.py                       # list problem ids
python tasks/frontier-cs/fetch.py 1 17                  # algorithmic track
python tasks/frontier-cs/fetch.py erdos_unit_distance   # 2.0 track
```

The algorithmic judge runs from a published image
(`yanagiorigami/frontier-cs-harbor-judge`), pulled on first use.
