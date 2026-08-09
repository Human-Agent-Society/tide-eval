# Build context for the separate verifier container (Harbor uses tests/ as
# the verifier env's build context in separate mode). Owns its own copy of
# the grading code at /tests — the agent container never sees it.
FROM python:3.12-slim

COPY . /tests
RUN chmod +x /tests/test.sh
