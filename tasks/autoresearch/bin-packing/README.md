# bin-packing

Pack 60 items into capacity-100 bins; reward = first-fit bins / yours.

| | |
|---|---|
| **Oracle (baseline)** | 1.0 (first-fit) |
| **Optimum** | > 1.0 (each bin saved) |
| **Run it** | `await lab.run("tasks/autoresearch/bin-packing", {"name": "oracle"})` |
| **Verify standalone** | `harbor trial start -p tasks/autoresearch/bin-packing` |

**What this task teaches:** Exact constraint checking: every item exactly once, no overfull bins — one violation scores zero.

Files: `instruction.md` (what the agent sees) · `environment/` (its world,
scorer included) · `tests/` (the separate-verifier grader + `vectors.json`
cheat suite) · `solution/` (the oracle baseline).
