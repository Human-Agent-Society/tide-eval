# Build context for the separate verifier container. Owns its own copy of
# the grading code at /tests — the agent container never sees it.
FROM python:3.12-slim
COPY . /tests
RUN chmod +x /tests/test.sh
