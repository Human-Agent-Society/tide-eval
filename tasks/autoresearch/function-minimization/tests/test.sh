#!/bin/bash
# Trusted verification entry point (SEPARATE verifier container; artifacts
# re-materialized at their original paths). Writes /logs/verifier/reward.json.
set -uo pipefail
mkdir -p /logs/verifier
python3 /tests/grade.py
