# triage-rca-agent

Multi-agent bug triage and root cause analysis for Python codebases.

```
$ triage-rca run --issue "TypeError in DataFrame.merge with nullable int columns" --repo ./pandas

[Triage]    issue_type:  confirmed_bug
            bug_type:    type_error
            severity:    high
            component:   core/reshape/merge.py
            similar:     3 past issues (score ≥ 0.87)
            recommend:   investigate_rca → running

[RCA]       Investigator  ████████░░  collecting evidence
            Docker test   ✓  exit 1, 4 frames captured
            Reasoner      ████████████  3 hypotheses ranked
            Verifier      ✓  top hypothesis confirmed

────────────────────────────────────────────────────
 #  File                          Lines    Confidence
────────────────────────────────────────────────────
 1  core/reshape/merge.py         847–863  0.91  ✓
 2  core/dtypes/cast.py           204–211  0.43
 3  core/frame.py                 3901     0.21
────────────────────────────────────────────────────
Cost: $0.18  |  Time: 43s  |  Tools: 34
```

## Results

| Metric | This system | Naive Claude | AGENTFL (Defects4J) |
|---|---|---|---|
| RCA Top-1 | — | — | 39.7% |
| RCA Top-3 | — | — | — |
| Triage accuracy | — | — | — |
| Cost / bug | — | — | $0.074 |
| Time / bug | — | — | 97s |

_Results pending eval run on BugsInPy subset. Baselines from published papers._

## Architecture

```
                        ┌─────────────────────────────┐
    bug report ────────▶│   Orchestrator (Opus 4.7)   │────▶ result.json
    + repo path         │   budget · routing · recovery│
                        └──────────┬──────────┬────────┘
                                   │          │
                         ┌─────────▼─┐    ┌───▼──────────┐
                         │  Triage   │    │     RCA       │
                         │  Pipeline │    │   Pipeline    │
                         └─────────┬─┘    └───┬──────────┘
                                   │          │
              ┌────────────────────┤          ├──────────────────────┐
              │                    │          │                      │
        Classifier           CodeExplorer  Investigator          Reasoner
        issue_type           component     Evidence Bundle       Hypothesis
        bug_type             detection     + Docker sandbox      ranking
        severity                           + static/dynamic
                         SimilaritySearcher  memory
                         sqlite-vec search                     Verifier
                                                               confirm /
                                                               demote
```

**Key invariants:**
- Subagents never communicate peer-to-peer — all state flows through Orchestrator
- Reasoner only sees the Evidence Bundle, never raw files
- Every run produces a Stop Condition result — no silent failures
- Budget enforced before each subagent dispatch: `$0.50` · `300s` · `200 tool calls`

## Requirements

- Python 3.11+
- Docker (running)
- Anthropic API key
- Langfuse account (free tier)

## Setup

```bash
pip install -r requirements.txt

cp .env.example .env
# fill in ANTHROPIC_API_KEY and LANGFUSE keys

python scripts/setup_db.py      # init DB + embed BugsInPy corpus (~500 bugs)
python scripts/setup_eval.py    # load 30-50 hand-labeled triage examples
```

## Usage

```bash
# Triage + RCA on any Python repo
triage-rca run --issue "..." --repo ./path/to/repo

# Interactive mode — agent pauses and asks for guidance when stuck
triage-rca run --issue "..." --repo ./path/to/repo --interactive

# Run evals
triage-rca eval rca       # Top-1/3/5 on BugsInPy subset
triage-rca eval triage    # accuracy on hand-labeled set
```

## Design

Built on the Anthropic SDK directly — no LangChain or LangGraph. The orchestrator loop, budget management, recovery hierarchy, and subagent dispatch are custom code. See [`docs/adr/`](docs/adr/) for why.

Full design rationale: [`docs/PRD.md`](docs/PRD.md) · [`CONTEXT.md`](CONTEXT.md)
