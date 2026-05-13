# Milestone 6: Rich CLI + Langfuse Observability

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live progress display during runs using Rich; Langfuse traces every Anthropic API call; `--interactive` pause works; final output shows a colored hypothesis ranking table compatible with asciinema recording.

**Deliverable Test:** Manual: `triage-rca run --issue "..." --repo ...` shows live spinner with subagent/tool/cost/time. Langfuse dashboard shows traces. `asciinema rec` captures the full session.

**Domain refs:** CONTEXT.md: Live Progress Display, Observability. CLAUDE.md: rich library, Langfuse.

**Prerequisite:** Milestones 1–5 complete.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/triage_rca/display.py` | `RunDisplay` with Rich Live panel + result table |
| Create | `src/triage_rca/langfuse_client.py` | Thin Langfuse wrapper: spans per API call + eval scoring |
| Modify | `src/triage_rca/agents/classifier.py` | Accept optional `LangfuseClient`, wrap `messages.create` |
| Modify | `src/triage_rca/agents/code_explorer.py` | Same |
| Modify | `src/triage_rca/agents/similarity_searcher.py` | Same |
| Modify | `src/triage_rca/agents/investigator.py` | Same |
| Modify | `src/triage_rca/agents/reasoner.py` | Same |
| Modify | `src/triage_rca/agents/verifier.py` | Same |
| Modify | `src/triage_rca/orchestrator.py` | Accept `RunDisplay`, fire events at stage boundaries |

---

## Display Layout (Rich Live)

```
┌─ triage-rca ─────────────────────────────────────────────────┐
│ Subagent:  Classifier              Cost:    $0.02             │
│ Tool:      —                       Elapsed: 12s               │
│                                                               │
│  ✓  issue_type:  confirmed_bug                                │
│  ✓  bug_type:    type_error                                   │
│  ⟳  CodeExplorer running...                                   │
└───────────────────────────────────────────────────────────────┘
```

Final result panel (printed after live display stops):

```
────────────────────────────────────────────────────────────────
 #  File                          Lines       Confidence
────────────────────────────────────────────────────────────────
 1  core/reshape/merge.py         847–863     0.91  ✓
 2  core/dtypes/cast.py           204–211     0.43
 3  core/frame.py                 3901        0.21
────────────────────────────────────────────────────────────────
Cost: $0.18  |  Time: 43s  |  Tools: 34
```

---

## RunDisplay Interface

```python
class RunDisplay:
    def start(self) -> None: ...
    def update_subagent(self, name: str) -> None: ...
    def update_tool(self, name: str) -> None: ...
    def update_cost(self, usd: float) -> None: ...
    def log_event(self, msg: str) -> None: ...
    def stop(self) -> None: ...
    def render_result(self, stop_condition: StopCondition) -> None: ...
```

---

## LangfuseClient Interface

```python
class LangfuseClient:
    def trace(self, name: str, run_id: str) -> Any: ...           # returns langfuse trace context
    def span(self, trace, name: str, input: dict) -> Any: ...     # returns span
    def end_span(self, span, output: dict, usage: dict) -> None: ...
    def score(self, run_id: str, name: str, value: float) -> None: ...
```

---

## Tasks

### T6.1: RunDisplay

- [ ] Create `src/triage_rca/display.py`:

```python
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from rich.text import Text
from triage_rca.schemas import StopCondition

console = Console()

class RunDisplay:
    def __init__(self):
        self._subagent = "—"
        self._tool = "—"
        self._cost = 0.0
        self._elapsed = 0.0
        self._events: list[str] = []
        self._live: Live | None = None

    def _build_panel(self) -> Panel:
        lines = [
            f"Subagent:  [bold]{self._subagent}[/bold]   Cost: [green]${self._cost:.3f}[/green]",
            f"Tool:      {self._tool}   Elapsed: {self._elapsed:.0f}s",
            "",
        ]
        lines += [f"  {e}" for e in self._events[-8:]]
        return Panel("\n".join(lines), title="[bold]triage-rca[/bold]", border_style="blue")

    def start(self) -> None:
        self._live = Live(self._build_panel(), refresh_per_second=4, console=console)
        self._live.start()

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._build_panel())

    def update_subagent(self, name: str) -> None:
        self._subagent = name
        self._tool = "—"
        self._refresh()

    def update_tool(self, name: str) -> None:
        self._tool = name
        self._refresh()

    def update_cost(self, usd: float) -> None:
        self._cost = usd
        self._refresh()

    def log_event(self, msg: str) -> None:
        self._events.append(msg)
        self._refresh()

    def stop(self) -> None:
        if self._live:
            self._live.stop()

    def render_result(self, sc: StopCondition) -> None:
        if not sc.hypotheses:
            console.print(f"\n[yellow]Status: {sc.status}[/yellow]  No hypotheses produced.")
            self._print_footer(sc)
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", width=3)
        table.add_column("File")
        table.add_column("Lines")
        table.add_column("Confidence")

        for i, h in enumerate(sc.hypotheses[:5], 1):
            check = " [green]✓[/green]" if h.verified else ""
            table.add_row(
                str(i),
                h.file,
                f"{h.start_line}–{h.end_line}",
                f"{h.confidence:.2f}{check}",
            )

        console.print(table)
        self._print_footer(sc)

    def _print_footer(self, sc: StopCondition) -> None:
        console.print(
            f"[dim]Cost: ${sc.cost_usd:.3f}  |  Time: {sc.elapsed_s:.1f}s  |  Tools: {sc.tool_calls_total}[/dim]"
        )
```

- [ ] Manual test: create `scripts/demo_display.py` and run it to verify layout looks correct:

```python
#!/usr/bin/env python3
import time
from triage_rca.display import RunDisplay
from triage_rca.schemas import StopCondition, Hypothesis

d = RunDisplay()
d.start()
d.update_subagent("Classifier")
time.sleep(0.5)
d.log_event("✓ issue_type: confirmed_bug")
d.log_event("✓ bug_type: type_error")
time.sleep(0.5)
d.update_subagent("CodeExplorer")
d.update_tool("read_file")
time.sleep(0.5)
d.update_cost(0.02)
d.log_event("⟳ CodeExplorer running...")
time.sleep(0.5)
d.stop()

sc = StopCondition(
    status="completed",
    triage_result=None,
    hypotheses=[
        Hypothesis("core/reshape/merge.py", 847, 863, 0.91, "No zero check", verified=True),
        Hypothesis("core/dtypes/cast.py", 204, 211, 0.43, "Type coercion"),
    ],
    partial=False, stop_reason="Done", steps_attempted=["triage", "rca"],
    cost_usd=0.18, elapsed_s=43.0, tool_calls_total=34,
)
d.render_result(sc)
```

Run: `python scripts/demo_display.py`
Verify: live panel shows, then hypothesis table renders correctly.

- [ ] Commit:

```bash
git add src/triage_rca/display.py scripts/demo_display.py
git commit -m "feat(m6): RunDisplay with Rich Live panel and hypothesis result table"
```

---

### T6.2: Langfuse Instrumentation

- [ ] Create `src/triage_rca/langfuse_client.py`:

```python
from langfuse import Langfuse

class LangfuseClient:
    def __init__(self, public_key: str, secret_key: str, host: str):
        self._lf = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )

    def trace(self, name: str, run_id: str):
        return self._lf.trace(name=name, id=run_id)

    def span(self, trace, name: str, input: dict):
        return trace.span(name=name, input=input)

    def end_span(self, span, output: dict, usage: dict | None = None) -> None:
        span.end(output=output, usage=usage or {})

    def score(self, run_id: str, name: str, value: float) -> None:
        self._lf.score(trace_id=run_id, name=name, value=value)

    def flush(self) -> None:
        self._lf.flush()
```

- [ ] Update each agent to accept optional `LangfuseClient`. Pattern (shown for Classifier, apply to all 5 agents):

In `src/triage_rca/agents/classifier.py`, change `__init__` and `classify`:

```python
class Classifier:
    def __init__(self, client: anthropic.Anthropic, lf: "LangfuseClient | None" = None):
        self.client = client
        self.lf = lf

    def classify(self, issue_text: str, trace=None) -> dict:
        span = self.lf.span(trace, "classifier", {"issue_text": issue_text[:200]}) if self.lf and trace else None
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": issue_text}],
        )
        result = json.loads(response.content[0].text)
        if span:
            usage = {"input": response.usage.input_tokens, "output": response.usage.output_tokens}
            self.lf.end_span(span, output=result, usage=usage)
        return result
```

Apply same pattern to CodeExplorer, Investigator, Reasoner, Verifier (SimilaritySearcher has no LLM call).

- [ ] Update `orchestrator.py` `run_pipeline()` to init and pass `LangfuseClient` + `RunDisplay`:

```python
def run_pipeline(issue: str, repo_path: str, interactive: bool = False) -> None:
    import uuid, os
    from triage_rca.config import load_config
    from triage_rca.display import RunDisplay
    from triage_rca.langfuse_client import LangfuseClient
    from triage_rca.db import init_db
    import anthropic

    config = load_config()
    db_path = os.getenv("TRIAGE_RCA_DB", "triage_rca.db")
    init_db(db_path)
    run_id = str(uuid.uuid4())

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    lf = LangfuseClient(config.langfuse_public_key, config.langfuse_secret_key, config.langfuse_host)
    display = RunDisplay()

    from triage_rca.issue_store import IssueStore
    from triage_rca.docker_sandbox import DockerSandbox
    from triage_rca.triage_pipeline import TriagePipeline
    from triage_rca.rca_pipeline import RCAPipeline

    store = IssueStore(db_path)
    sandbox = DockerSandbox()
    triage = TriagePipeline(client=client, issue_store=store, query_embedding=[0.0]*1024, lf=lf)
    rca = RCAPipeline(client=client, sandbox=sandbox, lf=lf)

    orch = Orchestrator(triage_pipeline=triage, rca_pipeline=rca, display=display)
    display.start()
    sc = orch.run(issue_text=issue, repo_path=repo_path, interactive=interactive, run_id=run_id)
    display.stop()
    display.render_result(sc)
    lf.flush()
```

- [ ] Manual verification with real API keys:

```bash
triage-rca run --issue "ZeroDivisionError in divide" --repo tests/fixtures/simple_repo
```

Open Langfuse dashboard → verify traces appear with model, input/output tokens, latency.

- [ ] Commit:

```bash
git add src/triage_rca/langfuse_client.py src/triage_rca/agents/ src/triage_rca/orchestrator.py
git commit -m "feat(m6): Langfuse instrumentation and RunDisplay wired into Orchestrator"
```

---

### T6.3: asciinema Recording Prep

- [ ] Verify asciinema is available: `which asciinema` or `brew install asciinema`

- [ ] Record demo:

```bash
asciinema rec demo.cast --title "triage-rca-agent demo"
triage-rca run --issue "TypeError in DataFrame.merge with nullable int columns" --repo /path/to/pandas-buggy
# Wait for result, then Ctrl+D to stop recording
```

- [ ] Verify playback: `asciinema play demo.cast`

- [ ] Add `demo.cast` to `.gitignore` (large binary, upload to asciinema.org separately):

```
echo "demo.cast" >> .gitignore
```

---

## Milestone 6 Verification

```bash
# Unit/integration tests still pass
pytest tests/ -v --ignore=tests/integration/test_docker_sandbox.py

# Manual smoke test with real keys
triage-rca run --issue "ZeroDivisionError in divide" --repo tests/fixtures/simple_repo
# Expected: live Rich display → result table → result.json written

# Langfuse: open dashboard, verify traces appear
# asciinema: record one session, verify playback works
```
