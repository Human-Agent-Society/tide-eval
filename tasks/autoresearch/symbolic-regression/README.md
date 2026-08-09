# symbolic-regression

Recover a hidden formula from samples; reward = 1/(1+RMSE) on HELD-OUT points.

| | |
|---|---|
| **Oracle (baseline)** | 0.604 (plain quadratic) |
| **Optimum** | 1.0 (the true formula) |
| **Run it** | `await lab.run("tasks/autoresearch/symbolic-regression", {"name": "oracle"})` |
| **Verify standalone** | `harbor trial start -p tasks/autoresearch/symbolic-regression` |

**What this task teaches:** The anti-overfitting wall: the agent optimizes against training points, the grader scores generalization. Expressions run through an AST whitelist, never eval().

Files: `instruction.md` (what the agent sees) · `environment/` (its world,
scorer included) · `tests/` (the separate-verifier grader + `vectors.json`
cheat suite) · `solution/` (the oracle baseline).
