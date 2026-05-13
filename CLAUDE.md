# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Multi-agent system for bug triage + root cause analysis on Python codebases. Portfolio project targeting internal developer tooling roles. See `draft.md` for framing, `CONTEXT.md` for domain language, `docs/adr/` for locked architectural decisions.

## Planned Stack

- **Runtime**: Python 3.11+
- **LLM**: Anthropic SDK directly — no LangChain/LangGraph (see ADR 0001)
- **Storage**: SQLite + sqlite-vec (`triage_rca.db`) — no Postgres/Redis (see ADR 0002)
- **Sandbox**: Docker for test execution (see ADR 0003)
- **Eval**: BugsInPy benchmark (see ADR 0004)
- **Observability**: Langfuse (cloud free tier)
- **CLI output**: `rich` library for live progress + structured results

## Planned Commands

```bash
# Setup
pip install -r requirements.txt
python scripts/setup_db.py          # init triage_rca.db + embed BugsInPy corpus
python scripts/setup_eval.py        # populate 30-50 hand-labeled triage eval examples

# Run
python -m triage_rca run --issue "..." --repo ./path/to/repo
python -m triage_rca run --issue "..." --repo ./path/to/repo --interactive   # HITL mode

# Eval
python -m triage_rca eval rca       # run RCA against BugsInPy subset, report Top-1/3/5
python -m triage_rca eval triage    # run triage against labeled eval set, report accuracy

# Single test
pytest tests/ -k "test_name"
```

## Architecture

Two agents sharing infrastructure, routed by a top-level Orchestrator:

```
Orchestrator (Opus 4.7)
├── Triage pipeline
│   ├── Classifier        — issue_type + bug_type + severity (no tools, pure LLM)
│   ├── CodeExplorer      — component detection (file read + grep tools)
│   └── SimilaritySearcher — nearest-neighbor over Issue Store (sqlite-vec)
└── RCA pipeline
    ├── Investigator      — codebase + Docker test execution → Evidence Bundle
    ├── Reasoner          — Evidence Bundle → ranked Hypothesis list (no file access)
    └── Verifier          — confirms or demotes top Hypothesis
```

**Key invariants:**
- Subagents never communicate peer-to-peer — all return to Orchestrator
- Reasoner never reads files directly — only receives the Evidence Bundle from Investigator
- Classifier always runs first and gates all downstream triage work
- Deterministic steps (embedding, DB writes) stay outside the agent loop

## Budget Enforcement

Orchestrator enforces per-run hard limits before each subagent dispatch:
- Cost: `$0.50`
- Wall-clock: `300s`
- Tool calls: `50` per subagent, `200` total

On breach: emit structured Stop Condition result (`budget_exceeded`, `timeout`) — never silent failure.

## Recovery Loop

Four levels, in order:
1. Local retry (tool call failure, ≤2 retries)
2. Plan amendment (subagent returns garbage)
3. Full replan (2+ subagents fail)
4. `request_human_review(reason, partial_result)` — blocks in `--interactive` mode, writes `escalation.json` and exits in eval mode

## Domain Language

Canonical terms are in `CONTEXT.md`. Key ones: **Bug Report**, **Issue Type**, **Bug Type**, **Hypothesis**, **Evidence Bundle**, **Static/Dynamic Memory**, **Stop Condition**, **Partial Result**. Use these exactly — don't invent synonyms.
