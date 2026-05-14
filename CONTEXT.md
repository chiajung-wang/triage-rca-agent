# Triage + RCA Agent — Domain Language

## Terms

### Bug Report
A natural-language description of unexpected behavior submitted against a Python codebase. May be a GitHub issue, a plain text description, or a failing test + stack trace. The primary input to both agents.

### Target Codebase
Any Python repository the system is run against. At eval time: a BugsInPy project. In production use: any Python codebase.

### BugsInPy
The eval benchmark. A curated dataset of real Python bugs with ground truth (buggy commit, fixed commit, triggering test). Used to measure RCA accuracy against known answers.

### Eval Set (Triage)
30-50 hand-labeled examples derived from BugsInPy bugs. Each entry: a GitHub-style issue description + ground truth `issue_type`, `bug_type`, `severity`, `component`. Used to measure Triage accuracy.

### RCA Eval Metric
Top-N accuracy: does the correct buggy file appear in the Reasoner's top-N Hypotheses? Primary metric: Top-1. Secondary: Top-3, Top-5.

### Run Output
Rich terminal output (via `rich` library): colored structured result showing triage classification, hypothesis ranking with confidence scores, and run metadata (cost, latency, tool calls). Also writes `result.json` to disk. Recorded as asciinema/GIF for README demo.

### Live Progress Display
Real-time terminal output during a run showing: current active subagent, current tool being called, cumulative cost and elapsed time. Implemented via `rich.Live` or streaming updates. User must never be looking at a silent terminal.

### Budget
Per-run hard limits enforced by Orchestrator: `$0.50` cost cap, `300s` wall-clock cap, `50 tool calls` per subagent / `200 total` per run. Orchestrator checks before each subagent dispatch; aborts with `budget_exceeded` stop condition if exceeded.

### Run State
Non-terminal initial state of a run:
- `running`: pipeline is executing; not yet complete

### Stop Condition
Named terminal state of a run. Always produces structured output — never silent failure.
- `completed`: full pipeline ran, Verifier confirmed ≥1 hypothesis
- `low_confidence`: Verifier demoted all hypotheses; outputs unverified top-3 as partial result
- `no_hypothesis`: Reasoner produced nothing actionable
- `budget_exceeded`: cost or tool-call cap hit
- `timeout`: wall-clock cap hit
- `escalated`: 2+ replans failed; outputs best partial result with full trace of what was attempted

### Partial Result
Output included in any non-`completed` stop condition. Contains: best available hypotheses (unverified if needed), stop reason, steps attempted, cost and latency consumed. Allows human to continue from where the agent stopped.

### request_human_review
Explicit escalation tool callable by the Orchestrator. Behavior differs by mode:
- `--interactive` mode: blocks, displays partial result + reason via `rich`, prompts for freetext feedback, continues run with feedback injected into Orchestrator context.
- eval mode (default): writes `escalation.json`, exits cleanly with `status: escalated`. Non-blocking — required for automated eval runs over 50 bugs.

### Triage
The act of classifying, scoping, and routing a Bug Report without locating the root cause. Output: `{ severity, bug_type, component, similar_issues[], recommendation }`. Recommendation drives pipeline flow — "investigate_rca" triggers the RCA agent in the same run.

### Triage Output
Structured result of the Triage agent:
- `severity`: critical / high / medium / low
- `bug_type`: taxonomy tag (see Bug Type)
- `component`: affected module/subsystem (inferred from codebase)
- `similar_issues`: list of past issues with similarity score
- `recommendation`: `investigate_rca` | `needs_repro` | `close_duplicate` | `needs_more_info`

### Issue Type
First-pass classification of a raw GitHub issue: `confirmed_bug` | `feature_request` | `question` | `documentation` | `security` | `enhancement`. If not `confirmed_bug` or `security`, triage may short-circuit with `needs_more_info` or `close_duplicate` recommendation without proceeding to Bug Type tagging.

### Bug Type
Root-cause category of a confirmed bug. Applied only when Issue Type is `confirmed_bug` or `security`. Taxonomy: `logic_error` | `type_error` | `null_handling` | `off_by_one` | `regression` | `concurrency` | `api_misuse` | `config_error` | `performance` | `import_error`.

### RCA (Root Cause Analysis)
The act of locating the specific code responsible for a Bug Report. Output is a ranked list of hypotheses (file + line range + confidence), not a fix.

### Hypothesis
A candidate root cause: a specific code location with a confidence score and supporting reasoning. RCA output is a ranked list of Hypotheses, not a single answer.

### Orchestrator
The top-level agent (Opus 4.7) that holds the plan, manages token/cost budget, routes between Triage and RCA, and decides recovery actions.

### Subagent
A scoped worker (Sonnet 4.6) dispatched by the Orchestrator for a specific subtask. Returns result to Orchestrator; no peer-to-peer communication.

### Classifier
Triage subagent. Reads issue text only. Outputs `issue_type` + `bug_type` + `severity`. No tools — pure LLM. Gates all downstream triage work.

### CodeExplorer
Triage subagent. Searches target codebase to identify affected `component`. Uses file read + grep tools. Only runs if Classifier returns `confirmed_bug` or `security`.

### SimilaritySearcher
Triage subagent. Queries the Issue Store to find similar issues with scores. Uses vector similarity retrieval tool. Runs in parallel with CodeExplorer.

### Issue Store
SQLite database with sqlite-vec extension. Contains embedded BugsInPy bug descriptions. Used by SimilaritySearcher for nearest-neighbor lookup. Populated once at setup time.

### Storage
Single SQLite file (`triage_rca.db`). Tables: `runs`, `hypotheses`, `triage_results`, plus sqlite-vec virtual table for embeddings. No Postgres, no Redis.

### Observability
Langfuse (cloud free tier). Every subagent call traced. Eval scores logged per run (`top1_accuracy`, `triage_accuracy`). Triage eval set stored as Langfuse dataset. Used to track improvement across runs during development.

### Portfolio Artifacts
Three deliverables: (1) GitHub README with high-level two-agent architecture diagram, asciinema demo GIF, eval results table leading with numbers. (2) Technical writeup (~1500 words) on design decisions and failures. (3) Eval results as README centerpiece — numbers vs naive Claude baseline and AGENTFL baseline. Writeup written after system works, not before.

### Investigator
RCA subagent. Explores codebase, stack traces, call paths to gather evidence. Heavy tool use. Can execute the triggering test inside a Docker sandbox to get live stack traces. Produces a structured Evidence Bundle.

### Evidence Bundle
Structured output of the Investigator. Contains: relevant code snippets (file + line), live stack trace (from Docker test run), call graph fragments, related test files, static memory snapshot, dynamic memory accumulated during investigation. Passed to Reasoner as sole input — Reasoner never reads files directly.

### Static Memory
Codebase facts built once at Investigator start: file tree, module index, test file location. Reused across all tool calls in the run to avoid redundant file reads.

### Dynamic Memory
Facts accumulated during Investigator's exploration: confirmed relevant files, stack frames, traced call path, ruled-out files. Appended as investigation proceeds. Serialized into Evidence Bundle.

### Docker Sandbox
Isolated Docker container used by Investigator to run the triggering test against the buggy commit. Produces live stack trace for dynamic evidence. Required local dependency.

### Reasoner
RCA subagent. Receives evidence bundle from Investigator. Generates ranked Hypothesis list. Minimal tools — mostly LLM reasoning. Never reads files directly.

### Verifier
RCA subagent. Checks top Hypothesis against triggering test / stack trace. Confirms or demotes. Final step before output.
