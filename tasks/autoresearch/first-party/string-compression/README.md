# string-compression

Ship a decompressor + payload; reward = corpus / compressed bytes, byte-exact round trip.

| | |
|---|---|
| **Oracle (baseline)** | 3.47 (zlib -9) |
| **Optimum** | higher (exploit the corpus structure) |
| **Run it** | `await lab.run("tasks/autoresearch/first-party/string-compression", {"name": "oracle"})` |
| **Verify standalone** | `harbor trial start -p tasks/autoresearch/first-party/string-compression` |

**What this task teaches:** Grading agent-shipped CODE safely: subprocess + timeout, and every corpus copy is deleted before the decompressor runs, so reading the reference scores zero.

Files: `instruction.md` (the problem + the submission protocol) ·
`environment/` (the agent's container, plus the judge: `score.py`, budget,
sidecar wiring) · `tests/grader_tests.json` (the scoring rule's cheat
suite) · `solution/` (the reference solution; submits once).
