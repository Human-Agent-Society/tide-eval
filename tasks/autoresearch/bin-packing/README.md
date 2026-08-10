# bin-packing

Pack 60 items into capacity-100 bins; reward = first-fit bins / yours.

| | |
|---|---|
| **Oracle (baseline)** | 1.0 (first-fit) |
| **Optimum** | > 1.0 (each bin saved) |
| **Run it** | `await lab.run("tasks/autoresearch/bin-packing", {"name": "oracle"})` |
| **Verify standalone** | `harbor trial start -p tasks/autoresearch/bin-packing` |

**What this task teaches:** Exact constraint checking: every item exactly once, no overfull bins — one violation scores zero.

Files: `instruction.md` (the problem + the submission protocol) ·
`environment/` (the agent's container, plus the judge: `score.py`, budget,
sidecar wiring) · `tests/grader_tests.json` (the scoring rule's cheat
suite) · `solution/` (the reference solution; submits once).
