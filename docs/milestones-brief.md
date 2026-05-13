# Milestone Brief

7 milestones, each in `docs/milestone-x/plan.md`. Build order is sequential — each milestone depends on the previous.

---

## M1 · Foundation
**Deliverable:** `pip install -e .` works, `triage-rca --help` prints usage, unit tests pass.

What gets built:
- `pyproject.toml` + `requirements.txt` — installable package, `triage-rca` entry point
- `src/triage_rca/config.py` — validates `.env` (ANTHROPIC_API_KEY, LANGFUSE_*)
- `src/triage_rca/budget.py` — BudgetTracker enforcing $0.50 / 300s / 50 tools/subagent / 200 total
- `src/triage_rca/db.py` + `scripts/setup_db.py` — SQLite schema: `runs`, `triage_results`, `hypotheses`
- `src/triage_rca/cli.py` — `run` and `eval` subcommands (stubs for now)

---

## M2 · Issue Store
**Deliverable:** Vector search works; BugsInPy descriptions embedded and queryable.

What gets built:
- `src/triage_rca/issue_store.py` — IssueStore using sqlite-vec; `insert()` / `search()` / `count()`
- `src/triage_rca/embedder.py` — `embed_text()` via voyage-3
- `scripts/setup_db.py` (updated) — inits sqlite-vec virtual table
- `scripts/embed_corpus.py` — loads BugsInPy bug.info files, embeds descriptions, inserts into store

---

## M3 · Triage Pipeline
**Deliverable:** `triage-rca run --issue "..." --repo .` returns a TriageResult with all fields.

What gets built:
- `src/triage_rca/schemas.py` — all shared dataclasses: TriageResult, Hypothesis, StopCondition, EvidenceBundle
- `src/triage_rca/agents/classifier.py` — pure LLM; outputs issue_type + bug_type + severity
- `src/triage_rca/agents/code_explorer.py` — file listing + LLM → component path
- `src/triage_rca/agents/similarity_searcher.py` — wraps IssueStore.search
- `src/triage_rca/triage_pipeline.py` — Classifier gates; confirmed_bug → CodeExplorer + SimilaritySearcher in parallel

Key invariant: non-bug issue_types (feature_request, question, etc.) short-circuit — CodeExplorer and SimilaritySearcher never run.

---

## M4 · RCA Pipeline
**Deliverable:** Investigator → Reasoner → Verifier produces ranked, verified Hypothesis list.

What gets built:
- `src/triage_rca/docker_sandbox.py` — `docker run` with repo mounted read-only; captures stdout/stderr; timeout-safe
- `src/triage_rca/memory_manager.py` — `build_static_memory()` → file tree + module index
- `src/triage_rca/agents/investigator.py` — builds StaticMemory, runs Docker, accumulates DynamicMemory → EvidenceBundle
- `src/triage_rca/agents/reasoner.py` — receives EvidenceBundle only (no file access); outputs ranked Hypothesis list
- `src/triage_rca/agents/verifier.py` — checks top Hypothesis vs stack trace; confirms or demotes (×0.3 confidence)
- `src/triage_rca/rca_pipeline.py` — wires the three subagents in sequence

Key invariant: Reasoner never reads files directly — EvidenceBundle is its sole input.

---

## M5 · Orchestrator
**Deliverable:** `triage-rca run` routes Triage → RCA, enforces budget, handles failures, writes `result.json`.

What gets built:
- `src/triage_rca/result_writer.py` — serializes StopCondition → `result.json`
- `src/triage_rca/orchestrator.py` — Orchestrator class: budget check before each dispatch, 4-level recovery, named StopConditions
- `run_pipeline()` — CLI entry that wires config + DB + pipelines into Orchestrator

Recovery levels (in order):
1. Local retry (tool failure, ≤2 attempts)
2. Plan amendment (simplified prompt, retry once)
3. Full replan (skip SimilaritySearcher, retry once)
4. `request_human_review` → writes `escalation.json` or blocks for stdin in `--interactive` mode

---

## M6 · Rich CLI + Langfuse
**Deliverable:** Live progress display during run; Langfuse traces all API calls; demo-recordable output.

What gets built:
- `src/triage_rca/display.py` — `RunDisplay` with Rich Live panel (subagent / tool / cost / elapsed) + final hypothesis table
- `src/triage_rca/langfuse_client.py` — thin wrapper: trace + span per `messages.create` call + `score()` for eval
- All 5 agents updated to accept optional `LangfuseClient` and fire spans
- Orchestrator updated to accept `RunDisplay` and fire events at stage boundaries

---

## M7 · Eval + Portfolio Polish
**Deliverable:** `eval rca` and `eval triage` commands produce real numbers; README table filled; writeup written.

What gets built:
- `src/triage_rca/eval_rca.py` — Top-N accuracy logic; iterates BugsInPy subset; writes `eval_rca_results.json`
- `src/triage_rca/eval_triage.py` — issue_type / bug_type / severity accuracy; writes `eval_triage_results.json`
- `src/triage_rca/eval.py` — dispatch: `triage-rca eval rca|triage`
- `scripts/setup_eval.py` + `data/eval/triage_eval.jsonl` — 17 hand-labeled triage examples
- `docs/writeup.md` — ~1500 word technical writeup (problem → decisions → results → failure modes)
- `README.md` — results table filled with real Top-1/3/5 and accuracy numbers
- `demo.cast` — asciinema recording linked from README

---

## Dependency Graph

```
M1 (Foundation)
 └─ M2 (Issue Store)
     └─ M3 (Triage Pipeline)
         └─ M4 (RCA Pipeline)
             └─ M5 (Orchestrator)
                 └─ M6 (Rich CLI + Langfuse)
                     └─ M7 (Eval + Portfolio)
```

## Quick Reference

| M | Key new files | Test command |
|---|---------------|--------------|
| 1 | budget.py, db.py, cli.py | `pytest tests/unit/` |
| 2 | issue_store.py, embedder.py | `pytest tests/unit/test_issue_store.py` |
| 3 | schemas.py, classifier.py, triage_pipeline.py | `pytest tests/integration/test_triage_pipeline.py` |
| 4 | docker_sandbox.py, investigator.py, rca_pipeline.py | `pytest tests/integration/test_rca_pipeline.py` |
| 5 | orchestrator.py, result_writer.py | `pytest tests/integration/test_orchestrator.py` |
| 6 | display.py, langfuse_client.py | manual: `triage-rca run --issue "..." --repo ...` |
| 7 | eval_rca.py, eval_triage.py, writeup.md | `triage-rca eval rca` + `triage-rca eval triage` |
