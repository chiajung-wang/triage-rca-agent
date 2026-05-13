# ADR 0003: Docker Sandbox for Test Execution

## Status
Accepted

## Context
The Investigator subagent needs to run the triggering test against the buggy commit to obtain a live stack trace for dynamic evidence. This requires executing untrusted code from arbitrary Python repos.

## Decision
Execute tests inside a Docker container. The Investigator dispatches `docker run` with the BugsInPy repo mounted, runs `pytest` against the buggy commit, captures stdout/stderr.

## Consequences
- Live stack traces are significantly more informative than static analysis alone — differentiates the system from pure LLM-over-code approaches
- Requires Docker as a local dependency (documented in README)
- E2B/Modal considered and rejected: cloud sandbox adds latency, cost, and account setup overhead that is not justified for a portfolio CLI tool
- Tradeoff: eval runs are slower (Docker container spin-up per bug); acceptable given the 300s wall-clock budget per run
