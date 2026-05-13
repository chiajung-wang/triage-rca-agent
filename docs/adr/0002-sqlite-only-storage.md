# ADR 0002: SQLite-only Storage

## Status
Accepted

## Context
The system needs to store run results, hypotheses, triage outputs, and vector embeddings for similarity search. Postgres + Redis were sketched as candidates.

## Decision
Use a single SQLite file (`triage_rca.db`) with the sqlite-vec extension for vector embeddings. No Postgres, no Redis.

## Consequences
- Zero infrastructure setup: clone repo, run — no Docker compose for the DB layer
- sqlite-vec handles nearest-neighbor search over BugsInPy embeddings without a separate vector store
- Bottleneck is LLM API latency (~seconds per call), not DB throughput — SQLite is not the constraint
- Tradeoff: no concurrent writers, no horizontal scaling — irrelevant for a CLI eval tool
- If a web dashboard is added later, migration to Postgres is straightforward; SQLite schema stays identical
