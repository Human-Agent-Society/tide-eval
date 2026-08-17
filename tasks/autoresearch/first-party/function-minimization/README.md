# function-minimization

Minimize the deceptive Levi N.13 function; reward = 1/(1+f).

| | |
|---|---|
| **Oracle (baseline)** | 1/3 (the origin) |
| **Optimum** | 1.0 (global minimum at (1,1)) |
| **Run it** | `await lab.run("tasks/autoresearch/first-party/function-minimization", {"name": "oracle"})` |
| **Verify standalone** | `harbor trial start -p tasks/autoresearch/first-party/function-minimization` |

**What this task teaches:** Deceptive landscapes: local search stalls, the agent must explore. Cheap to grade, instant to iterate.

Files: `instruction.md` (the problem + the submission protocol) ·
`environment/` (the agent's container, plus the judge: `score.py`, budget,
sidecar wiring) · `tests/grader_tests.json` (the scoring rule's cheat
suite) · `solution/` (the reference solution; submits once).
