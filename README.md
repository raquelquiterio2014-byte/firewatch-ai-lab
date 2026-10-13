# FireWatch AI — V1

**Educational multi-agent prototype for fire-indicator analysis, evidence traceability and human review.**

Developed by **Raquel Cruz** as a separate practice project for learning Cursor before the Open Agent Hackathon 2026. Inspired by the evidence, critic and human-gate structure of ResilientCity AI.

FireWatch evaluates **supplied observations** about vegetation and the urban–vegetation interface. It distinguishes fire indications, contextual priority and evidence gaps. It does not independently diagnose a fire, forecast propagation, issue operational commands or establish that an area is safe.

## V1 — From a Form to a Traceable Workflow

This milestone adds readable component summaries in **Agents** and a typed completed-run snapshot in **State**, including human-review records. Package version: **1.1.0**. The V0 built locally in Cursor may differ from this repository: use [the V1 Cursor prompt](docs/V1_CURSOR_PROMPT.md) to evolve that code without assuming identical files.

## What is implemented

- English Tkinter/ttk desktop interface with scenarios and custom observations.
- Typed input and output models using Pydantic.
- Ten labelled synthetic scenarios and an evaluation screen.
- Planner, Evidence, Fire Assessment, Risk/Exposure, Decision, Critic and Reporter components.
- Deterministic Safety Gate and recorded human approval/rejection.
- SQLite run snapshots, evidence records, saved-run history and real JSONL trace events.
- TXT report and JSON run/evaluation export.
- Optional Gemini adapter with structured outputs, bounded retries and explicit fallback.
- Windows launcher, Cursor project rules and a GitHub Actions workflow.

## Two execution modes

**Deterministic:** works without an API key. It is a modular reference pipeline, not autonomous LLM reasoning. Rules are educational project hypotheses.

**Gemini hybrid:** Planner chooses one authorized analysis route, Decision drafts a structured review proposal, and Critic approves or requests revision. The selected route is executed and logged. Fire assessment, contextual priority, evidence checks and Safety Gate remain deterministic. At most one revision is allowed; each API call has at most two attempts with a 20-second request timeout. Missing credentials, provider/network failures or invalid output cause fallback and mandatory review.

`request_information_then_assess` records pending human information; it does not contact an external source and does not invent missing data. The application still analyzes the available observation with explicit unknowns.

The orchestrator is implemented in Python; **LangGraph is not yet integrated**. There is no camera, sensor ingestion, automatic contradiction extraction, MCP server, geospatial layer or live fire-data integration in this release.

## Run on Windows

Install Python 3.11 or later with Tkinter support. Extract or clone the project, open the folder in Cursor, then use its terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Alternatively, after installing requirements, double-click `run_gui.bat`. It uses the local `.venv` if present, otherwise the Windows Python launcher.

No activation or PowerShell execution-policy change is required. On Linux, install the distribution's Tkinter package if it is absent.

### Optional Gemini

Set the key in the same terminal before launching. The app reads environment variables; it **does not automatically load `.env`**.

```powershell
$env:GEMINI_API_KEY = "YOUR_KEY"
$env:GEMINI_MODEL = "gemini-2.5-flash"
.\.venv\Scripts\python.exe main.py
```

Select **Use Gemini (optional)** in the GUI. Model availability and structured-output support depend on the provider/account. Do not put a real key in source files or commits. The default model is configurable; a live provider call has not been validated in the development environment.

## Interface

| Tab | Purpose |
|---|---|
| Incident | Scenario selector, normalized observations, source/provenance and saved-run history |
| Agents | Actual component results, selected plan, critic verdict and revision count |
| Evidence | Record IDs, source, method, provenance, age, unknown fields and flagged conflicts |
| Safety / Review | Mandatory review reasons and reviewer/comment records |
| Report | Explainable TXT report and JSON export |
| Trace | Actual events linked to the current run ID |
| State | Validated snapshot of completed component outputs and recorded human reviews |
| Evaluation | Ten deterministic synthetic cases and expected-versus-actual fields |

The GUI accepts one evidence record per new manual analysis. The backend supports multiple evidence records. Normalized form fields drive the reference rules: free text is **not automatically extracted**. Conflict flags and provenance are entered declarations, not independent verification.

When editing a loaded run, run a new analysis to create a new immutable run snapshot. Recorded human approval does not erase the Safety Gate result. JSON export includes human-review records separately from the original analysis snapshot.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --evaluate --output exports\evaluation.json
.\.venv\Scripts\python.exe main.py --scenario 3 --output exports\flames-case.json
```

The evaluation uses deterministic mode even if a key exists. Use `--scenario 3 --llm` explicitly for a provider-backed CLI run. Data is stored in `data/` by default; change it with `--data-dir`.

Tests cover invalid values, unknowns, timestamp validation, stale/conflicting records, fire indications and exposure, bounded revision, invented evidence IDs, removal of required review, fallback, run persistence and worker-thread database access. LLM tests use **offline test doubles**, not a real Gemini invocation.

Validation status and limitations: [docs/VALIDATION.md](docs/VALIDATION.md). Architecture and rules: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Cursor exercises: [docs/CURSOR_WORKFLOW.md](docs/CURSOR_WORKFLOW.md).

The original implementation passed [GitHub Actions on Python 3.11 and 3.12](https://github.com/raquelquiterio2014-byte/firewatch-ai-lab/actions/runs/38315261731). V1 adds three tests for state preservation and readable summaries; the local suite now has 25 passing tests. Remote CI must be checked for the V1 commit separately.

## Rule interpretation

- Flames in the observation → `STRONG_INDICATION`, qualified by evidence provenance.
- Smoke without reported flames → `POSSIBLE_FIRE`; cause remains unknown.
- Explicitly absent smoke and flames → `NO_INDICATION` in the supplied observation only.
- Partial/unknown indicators → `INSUFFICIENT_EVIDENCE`.
- Fire indications and exposure → `HIGH` contextual priority, mandatory review.
- Fire indications with unknown exposure → `UNDETERMINED`, mandatory review.
- Fire indications with no reported exposure → `MEDIUM`, mandatory review in this conservative educational release.
- Unknown fields, manually flagged conflicts, observations older than six hours, future timestamps, unresolved criticism or LLM errors → mandatory review.

The six-hour age policy and priority labels are demonstration choices, not scientifically calibrated thresholds. Dry vegetation or low humidity alone never confirms a fire. No confidence percentages are displayed.

## References

- Cursor project rules: https://cursor.com/docs/rules
- Gemini structured output: https://ai.google.dev/gemini-api/docs/generate-content/structured-output

This repository's scenarios contain no real incidents or measured sensor records. Synthetic agreement demonstrates consistency with project rules, not field accuracy.
