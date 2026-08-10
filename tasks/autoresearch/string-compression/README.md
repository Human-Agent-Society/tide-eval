# string-compression

Ship a decompressor + payload; reward = corpus / compressed bytes, byte-exact round trip.

| | |
|---|---|
| **Oracle (baseline)** | 3.47 (zlib -9) |
| **Optimum** | higher (exploit the corpus structure) |
| **Run it** | `await lab.run("tasks/autoresearch/string-compression", {"name": "oracle"})` |
| **Verify standalone** | `harbor trial start -p tasks/autoresearch/string-compression` |

**What this task teaches:** Grading agent-shipped CODE safely: subprocess + timeout, and every corpus copy is deleted before the decompressor runs — reading the reference scores zero.

Files: `instruction.md` (what the agent sees) · `environment/` (its world,
scorer included) · `tests/` (the separate-verifier grader + `grader_tests.json`
cheat suite) · `solution/` (the oracle baseline).
