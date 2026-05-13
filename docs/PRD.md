# PRD: Triage + RCA Agent

_Last updated: 2026-05-13_

---

## Problem Statement

Debugging production bugs is slow. A developer receives a GitHub issue or bug report, manually triages it (is it real? how severe? what component?), then spends significant time searching the codebase for the root cause — reading stack traces, tracing call paths, reading related files. This context-gathering phase consumes the majority of debugging time (research shows coding agents spend 60%+ of time searching for context), and the result is still often a guess rather than a verified hypothesis.

Existing commercial tools (Sentry Seer, Rollbar RCA) are tightly coupled to their own observability platforms. Open-source alternatives either require framework lock-in (LangGraph) or don't produce verifiable, ranked hypotheses. Developers working on arbitrary Python codebases have no lightweight, portable tool that automates triage + root cause localization end-to-end.

---

## Solution

A CLI tool that takes a bug report (GitHub issue text or freetext description) and a path to any Python repository, and produces:

1. A structured **Triage Result**: issue type, bug type, severity, affected component, similar past issues
2. A ranked **Hypothesis List**: top candidate root-cause locations (file + line range + confidence score), verified against the triggering test

The tool runs a multi-agent pipeline internally — an Orchestrator routes between a Triage pipeline and an RCA pipeline, each composed of focused subagents. The user sees live progress in the terminal and receives a structured `result.json` at the end. The system never silently fails: every run produces a named Stop Condition with a Partial Result if the full pipeline cannot complete.

---

## User Stories

### Setup

1. As a developer, I want to install the tool with `pip install` and run it immediately, so that setup does not block me from trying it on a real bug.
2. As a developer, I want a single `setup_db.py` script that initializes the database and embeds the BugsInPy corpus, so that I only need to run it once.
3. As a developer, I want a `.env.example` file listing all required environment variables, so that I know exactly what API keys to provide.
4. As a developer, I want the tool to validate that Docker is running at startup, so that I get a clear error before a run fails mid-way.
5. As a developer, I want the tool to validate my Anthropic and Langfuse API keys at startup, so that I get a clear error before spending money on a broken run.

### Triage

6. As a developer, I want to submit a raw GitHub issue (including non-bugs like feature requests and questions), so that the tool can tell me whether it warrants further investigation.
7. As a developer, I want the Triage agent to classify the issue type (`confirmed_bug`, `feature_request`, `question`, `documentation`, `security`, `enhancement`), so that I can quickly filter noise.
8. As a developer, I want the Triage agent to tag a confirmed bug with a bug type (`logic_error`, `type_error`, `null_handling`, `off_by_one`, `regression`, `concurrency`, `api_misuse`, `config_error`, `performance`, `import_error`), so that I understand the nature of the defect before diving in.
9. As a developer, I want the Triage agent to assign a severity level (`critical`, `high`, `medium`, `low`), so that I can prioritize my queue.
10. As a developer, I want the Triage agent to identify the affected component (module or subsystem) by examining the target codebase, so that I know where to look.
11. As a developer, I want the Triage agent to surface similar past issues with similarity scores, so that I can see if this has been seen before.
12. As a developer, I want the Triage agent to emit a recommendation (`investigate_rca`, `needs_repro`, `close_duplicate`, `needs_more_info`), so that I know what the next step is without reading the full output.
13. As a developer, I want non-bug issues to short-circuit without running RCA, so that I don't pay for unnecessary LLM calls.

### RCA

14. As a developer, I want the RCA agent to run the triggering test against the buggy code in a Docker container, so that it has a live stack trace rather than relying on static analysis alone.
15. As a developer, I want the Investigator to build a static memory snapshot (file tree, module index) at the start of each run, so that it doesn't redundantly re-read the same files.
16. As a developer, I want the Investigator to accumulate a dynamic memory of findings (relevant files, stack frames, call path, ruled-out files) as it explores, so that the Reasoner receives a complete evidence picture.
17. As a developer, I want the Reasoner to receive only the Evidence Bundle and never access files directly, so that reasoning is always grounded in structured evidence rather than free-form file browsing.
18. As a developer, I want the output to be a ranked list of Hypotheses (file + line range + confidence + reasoning), so that I can evaluate multiple candidates rather than trusting a single answer.
19. As a developer, I want the Verifier to check the top Hypothesis against the triggering test and stack trace, so that I have a confirmed or demoted result before the run ends.
20. As a developer, I want unverified top-3 hypotheses included in the output when the Verifier demotes all candidates, so that I still have useful leads even when the agent cannot confirm a root cause.

### CLI and Output

21. As a developer, I want a live progress display in the terminal showing the current active subagent, current tool call, cumulative cost, and elapsed time, so that I am never looking at a silent terminal during a run.
22. As a developer, I want a `--interactive` flag that pauses the run and prompts for human input when the Orchestrator calls `request_human_review`, so that I can redirect the agent mid-run.
23. As a developer, I want every run to write a `result.json` to disk regardless of outcome, so that I can inspect the full structured result after the terminal clears.
24. As a developer, I want the terminal output to be formatted with `rich` (colored tables, confidence bars, component labels), so that I can record it as a GIF for the README.
25. As a developer, I want the run output to include cost, latency, and tool-call count metadata, so that I can compare efficiency across runs.
26. As a developer, I want failed runs to produce a `result.json` with `status: escalated` and a full trace of what was attempted, so that no run is wasted.

### Budget and Recovery

27. As a developer, I want the Orchestrator to enforce a `$0.50` per-run cost cap, so that a runaway agent cannot drain my API budget.
28. As a developer, I want the Orchestrator to enforce a `300s` wall-clock cap, so that a hung run terminates automatically.
29. As a developer, I want per-subagent tool-call caps (`50`) and a total run cap (`200`), so that infinite-loop scenarios are bounded.
30. As a developer, I want the Orchestrator to attempt a local retry (up to 2x) when a single tool call fails, before escalating, so that transient errors don't abort the run.
31. As a developer, I want the Orchestrator to amend its plan when a subagent returns unusable output, so that one bad subagent result doesn't terminate the run.
32. As a developer, I want the Orchestrator to trigger a full replan after 2+ subagent failures, so that it can recover from compounding errors.
33. As a developer, I want the Orchestrator to call `request_human_review` with a Partial Result after 2 failed replans, so that I receive the best available output and an explanation of what failed.

### Eval

34. As a developer, I want a `triage_rca eval rca` command that runs RCA against a BugsInPy subset and reports Top-1, Top-3, Top-5 accuracy, so that I can measure improvement over time.
35. As a developer, I want a `triage_rca eval triage` command that runs triage against my 30-50 hand-labeled examples and reports classification accuracy per field, so that I can measure triage quality.
36. As a developer, I want eval runs to log scores to Langfuse automatically, so that I can see accuracy trends across development sessions.
37. As a developer, I want eval runs to be non-blocking (no `--interactive` pauses), so that I can run the full benchmark unattended.
38. As a developer, I want to compare my results against a naive Claude baseline (single Sonnet call, no scaffold), so that I can quantify the value of the multi-agent harness.

### Observability

39. As a developer, I want every subagent API call traced in Langfuse with inputs, outputs, and latency, so that I can debug unexpected agent behavior.
40. As a developer, I want the triage eval set stored as a Langfuse dataset, so that I can manage and expand it from the Langfuse UI.
41. As a developer, I want per-run cost and latency visible in Langfuse, so that I can track efficiency regressions.

---

## Implementation Decisions

### Modules

**1. Orchestrator**
Top-level agent (Opus 4.7). Holds the plan, manages budget state, routes between Triage and RCA pipelines, enforces recovery levels (local retry → plan amendment → full replan → `request_human_review`). Checks budget before every subagent dispatch. In `--interactive` mode, blocks on `request_human_review` and injects human feedback into the next plan step.

**2. Triage Pipeline**
Sequential: Classifier runs first (gating step) → if `confirmed_bug` or `security`, CodeExplorer and SimilaritySearcher run in parallel → results merged into Triage Result. Classifier is pure LLM with no tools. CodeExplorer uses file read + grep. SimilaritySearcher queries the Issue Store.

**3. RCA Pipeline**
Sequential: Investigator → Reasoner → Verifier. Investigator builds Static Memory at start, accumulates Dynamic Memory during exploration, and runs the triggering test in Docker Sandbox. Passes Evidence Bundle to Reasoner. Verifier checks top Hypothesis against stack trace and test output.

**4. Issue Store**
SQLite database (`triage_rca.db`) with sqlite-vec virtual table. Contains embedded BugsInPy bug descriptions. Populated once via `setup_db.py`. Exposes a `search(query_embedding, k) -> List[SimilarIssue]` interface. The entire BugsInPy corpus is embedded at setup time; no streaming updates during runs.

**5. Docker Sandbox**
Manages container lifecycle for test execution. Interface: `run_test(repo_path, commit_sha, test_file) -> TestResult(stdout, stderr, exit_code)`. Mounts the target repo read-only. Captures stdout/stderr for stack trace extraction. Wall-clock timeout enforced at container level independent of the agent budget.

**6. Budget Tracker**
Stateful object passed through the Orchestrator. Tracks cumulative token cost (using Anthropic usage response fields), wall-clock elapsed time, and tool call counts (per-subagent and total). Raises `BudgetExceeded` when any limit is hit. Orchestrator checks before dispatch, not after.

**7. Memory Manager**
Two structures per run. Static Memory: built once at Investigator start via `build_static_memory(repo_path) -> StaticMemory` (file tree, module index, test file location). Dynamic Memory: a mutable dict appended during the Investigator's tool calls. Both serialized into the Evidence Bundle.

**8. Rich CLI / Progress Display**
Uses `rich.Live` with a layout showing: current subagent name, current tool name, cumulative cost, elapsed time, and a status log. Rendered throughout the run. Final output is a formatted panel with Triage Result + Hypothesis ranking table. All output is compatible with asciinema recording.

**9. Eval Harness**
Two eval modes: `rca` (iterates BugsInPy subset, calls full pipeline, checks if correct file appears in top-N hypotheses) and `triage` (iterates hand-labeled eval set, calls triage pipeline, compares output fields to ground truth). Logs scores to Langfuse. Runs in non-interactive eval mode (no HITL pauses). Reports aggregate accuracy to terminal.

**10. Langfuse Instrumentation**
Thin wrapper around Anthropic SDK calls. Every `messages.create` call wrapped in a Langfuse span with model, input tokens, output tokens, latency. Eval scores logged via `langfuse.score()`. Triage eval dataset managed as a Langfuse dataset. Instrumentation is additive — removing it does not change agent behavior.

### Key Contracts

**Evidence Bundle** (Investigator → Reasoner):
```
{
  "static_memory": { "file_tree": [...], "module_index": {...}, "test_file": "..." },
  "dynamic_memory": {
    "relevant_files": [...],
    "stack_frames": [...],
    "call_path": [...],
    "ruled_out": [...]
  },
  "code_snippets": [{ "file": "...", "start_line": N, "end_line": N, "content": "..." }],
  "test_result": { "stdout": "...", "stderr": "...", "exit_code": N }
}
```

**Hypothesis** (Reasoner → Verifier → output):
```
{
  "file": "src/module.py",
  "start_line": N,
  "end_line": N,
  "confidence": 0.0–1.0,
  "reasoning": "..."
}
```

**Stop Condition** (all terminal states):
```
{
  "status": "completed" | "low_confidence" | "no_hypothesis" | "budget_exceeded" | "timeout" | "escalated",
  "triage_result": { ... },
  "hypotheses": [...],       # best available, may be unverified
  "partial": true | false,
  "stop_reason": "...",
  "steps_attempted": [...],
  "cost_usd": N,
  "elapsed_s": N,
  "tool_calls_total": N
}
```

### Architectural Constraints
- Reasoner never reads files directly — Evidence Bundle is its sole input
- Classifier always runs before CodeExplorer and SimilaritySearcher
- Deterministic operations (embedding, DB writes, Docker invocation) live outside the agent message loop
- Subagents never communicate peer-to-peer — all state flows through Orchestrator
- Budget Tracker is checked before dispatch, not after — no subagent can exceed limits by completing

---

## Testing Decisions

Good tests verify external behavior through the module's public interface. They do not assert on internal state, intermediate tool calls, or the specific LLM response text — only on the structured outputs the module produces.

### Modules to test

**Issue Store** — unit tests. Seed with known embeddings, assert nearest-neighbor results match expected IDs and score ordering. No LLM involved; fully deterministic.

**Budget Tracker** — unit tests. Verify that `BudgetExceeded` is raised at exactly the right thresholds for cost, wall-clock, and tool-call counts. Verify partial accumulation across multiple calls.

**Docker Sandbox** — integration tests. Run a known-failing test fixture, assert that `exit_code != 0` and `stderr` contains the expected exception type. Run a known-passing test, assert `exit_code == 0`. Requires Docker.

**Memory Manager** — unit tests. Build Static Memory against a small synthetic repo fixture, assert expected file tree shape and module index entries. Assert Dynamic Memory append behavior.

**Eval Harness** — integration tests. Run eval against a 3-bug BugsInPy micro-subset with a mock Anthropic client that returns fixed Hypothesis lists. Assert Top-1/3/5 accuracy computation is correct.

**Rich CLI** — not unit tested. Verified manually via terminal recording before each release.

**Orchestrator recovery loop** — integration tests with mock subagents. Inject failures at specific steps, assert that the correct recovery level is triggered and the correct Stop Condition is emitted.

---

## Out of Scope

- Fixing bugs or opening PRs — the system diagnoses, it does not resolve
- Support for non-Python codebases (Java, TypeScript, etc.)
- Web dashboard or frontend UI
- GitHub Actions / CI integration
- Cloud-hosted execution (E2B, Modal) — Docker local only
- Real-time GitHub issue webhook ingestion
- Multi-repo or monorepo awareness
- Per-user auth or multi-tenant usage
- Postgres, Redis, or any storage beyond SQLite

---

## Further Notes

**Build order**: Triage pipeline first (Classifier → CodeExplorer → SimilaritySearcher), then RCA pipeline (Investigator → Reasoner → Verifier), then wire Orchestrator routing between them. Eval harness built in parallel with each pipeline.

**Portfolio framing**: The system is intentionally over-engineered relative to what a single Sonnet call could do. The engineering choices (custom harness, explicit recovery levels, static+dynamic memory, Docker dynamic analysis) exist to provide 45 minutes of interview depth — each is a deliberate decision with a defensible rationale documented in `docs/adr/`.

**Baselines for README**: Naive Claude (single Sonnet call), AGENTFL/MemFL published numbers, GitHub native AI triage Action. README leads with the numbers table.
