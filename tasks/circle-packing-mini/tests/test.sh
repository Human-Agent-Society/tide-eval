#!/bin/bash
# Trusted verification entry point. Runs in a SEPARATE container (see
# task.toml [verifier] environment_mode) that received only the declared
# artifacts under /logs/artifacts. Writes /logs/verifier/reward.json.
set -uo pipefail

mkdir -p /logs/verifier
python3 /tests/grade.py
