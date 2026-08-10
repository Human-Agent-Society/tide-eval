# tsp-tour

Shortest closed tour over 40 fixed cities; reward = identity length / yours.

| | |
|---|---|
| **Oracle (baseline)** | 1.0 (identity tour) |
| **Optimum** | ~2.0 (strong heuristics) |
| **Run it** | `await lab.run("tasks/autoresearch/tsp-tour", {"name": "oracle"})` |
| **Verify standalone** | `harbor trial start -p tasks/autoresearch/tsp-tour` |

**What this task teaches:** Classic combinatorial search with a continuous improvement signal — 2-opt and beyond.

Files: `instruction.md` (what the agent sees) · `environment/` (its world,
scorer included) · `tests/` (the separate-verifier grader + `grader_tests.json`
cheat suite) · `solution/` (the oracle baseline).
