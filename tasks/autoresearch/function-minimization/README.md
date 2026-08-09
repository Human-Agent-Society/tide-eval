# function-minimization

Minimize the deceptive Levi N.13 function; reward = 1/(1+f).

| | |
|---|---|
| **Oracle (baseline)** | 1/3 (the origin) |
| **Optimum** | 1.0 (global minimum at (1,1)) |
| **Run it** | `await lab.run("tasks/autoresearch/function-minimization", {"name": "oracle"})` |
| **Verify standalone** | `harbor trial start -p tasks/autoresearch/function-minimization` |

**What this task teaches:** Deceptive landscapes: local search stalls, the agent must explore. Cheap to grade, instant to iterate.

Files: `instruction.md` (what the agent sees) · `environment/` (its world,
scorer included) · `tests/` (the separate-verifier grader + `vectors.json`
cheat suite) · `solution/` (the oracle baseline).
