# FireWatch AI — V3

**Educational multi-agent prototype for fire-indicator analysis, evidence traceability and human review.**

Developed by **Raquel Cruz** as an educational project inspired by the evidence, critic and human-gate structure of ResilientCity AI. **Windows and PyCharm are the chosen environment for local execution and validation.**

FireWatch evaluates **supplied observations** about vegetation and the urban–vegetation interface. It distinguishes fire indications, contextual priority and evidence gaps. It does not independently diagnose a fire, forecast propagation, issue operational commands or establish that an area is safe.

## V3 — Supervised Pilot Evaluation

Package version: **3.0.0**. V3 keeps the LangGraph conditional workflow and adds a persisted evaluation dashboard: ten synthetic cases, two trials per case, an executable simplified checklist baseline, field agreement, missed/extra review counts, citation-ID validity and repeated-decision stability.

**Evaluation** presents summary cards, a per-case table, expected/actual fields, saved pilot history and links to each completed analysis. Export the comparison as JSON or CSV. **Evidence** now has a table showing source, method, declared provenance, timestamps and flags; completeness remains descriptive, not confidence.

The sample catalogue yields system agreement **10/10**, simplified checklist agreement **7/10**, system missed/extra reviews **0/0**, and repeated decisions **10/10**. The authored labels follow the richer system's rules; this is not an independent field-accuracy study or a comparison against observed professional human decisions.

Windows and PyCharm remain the local validation environment. Start without a key. Download the current version into a separate folder and preserve earlier folders/data. Existing run snapshots remain readable; the database adds a table for V3 pilot records.

V3 installation, protocol and metric definitions: [docs/V3_WINDOWS.md](docs/V3_WINDOWS.md).

## What is implemented

- English Tkinter/ttk desktop interface with scenarios and custom observations.
- Typed input and output models using Pydantic and a LangGraph workflow state.
- Ten labelled synthetic scenarios with a persisted pilot evaluation dashboard and two deterministic trials per case.
- Conditional workflow view, streamed state snapshots and descriptive evidence-quality checks.
- Planner, Evidence, Fire Assessment, Risk/Exposure, Decision, Critic and Reporter components.
- Deterministic Safety Gate and recorded human approval/rejection.
- SQLite run snapshots, evidence records, saved-run history and real JSONL trace events.
- TXT reports, JSON run/evaluation export and CSV evaluation tables.
- Executable checklist comparison, per-field agreement, missed/extra review counts and trial-linked history.
- Optional Gemini adapter with structured outputs, bounded retries and explicit fallback.
- Windows launcher and a GitHub Actions workflow.

## Two execution modes

**Deterministic:** works without an API key. LangGraph runs rule-based specialist nodes; graph orchestration itself does not create autonomous LLM reasoning. Rules remain educational project hypotheses.

**Gemini hybrid:** Planner chooses one authorized analysis route, Decision drafts a structured review proposal, and Critic approves or requests revision. The selected route is executed and logged. Fire assessment, contextual priority, evidence checks and Safety Gate remain deterministic. At most one revision is allowed; each API call has at most two attempts with a 20-second request timeout. Missing credentials, provider/network failures or invalid output cause fallback and mandatory review.

`request_information_then_assess` records pending human information; it does not contact an external source and does not invent missing data. The application still analyzes the available observation with explicit unknowns.

The orchestrator uses **LangGraph 1.2.15**, pinned in requirements.txt. There is no camera, sensor ingestion, automatic contradiction extraction, MCP server, geospatial layer or live fire-data integration in this release.

## Run on Windows with PyCharm

Install Python 3.11 or later with Tkinter support. Download or clone the current repository, extract it if necessary, and open the folder containing `main.py` as a project in PyCharm. Run the following commands in the PyCharm terminal from that project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

After creating the environment, configure the PyCharm project interpreter to use `.venv\Scripts\python.exe`. Run `main.py` with the working directory set to the project folder, so `data/` and exports are created in the intended location.

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
| Workflow | Compiled node topology, visited route and live completion updates |
| Evidence | Source/provenance inspector plus descriptive completeness, timestamps and flagged conflicts |
| Safety / Review | Mandatory review reasons and reviewer/comment records |
| Report | Explainable TXT report and JSON export |
| Trace | Actual events linked to the current run ID |
| State | Intermediate graph snapshots during execution; validated final outputs and human reviews afterward |
| Evaluation | Saved pilot dashboard, baseline comparison, repeated trials, per-case inspection and JSON/CSV export |

The GUI accepts one evidence record per new manual analysis. The backend supports multiple evidence records. Normalized form fields drive the reference rules: free text is **not automatically extracted**. Conflict flags and provenance are entered declarations, not independent verification.

When editing a loaded run, run a new analysis to create a new immutable run snapshot. Recorded human approval does not erase the Safety Gate result. JSON export includes human-review records separately from the original analysis snapshot.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --evaluate --repetitions 2 --output exports\evaluation.json --csv exports\evaluation.csv
.\.venv\Scripts\python.exe main.py --scenario 3 --output exports\flames-case.json
```

The evaluation uses deterministic mode even if a key exists. Use `--scenario 3 --llm` explicitly for a provider-backed CLI run. Data is stored in `data/` by default; change it with `--data-dir`.

Tests cover invalid values, unknowns, timestamp validation, stale/conflicting records, fire indications and exposure, bounded revision, invented evidence IDs, removal of required review, fallback, run persistence and worker-thread database access. LLM tests use **offline test doubles**, not a real Gemini invocation.

### Local visual validation in PyCharm

Start with **Use Gemini (optional)** unchecked. Analyze **03 — Flames near people** and confirm `STRONG_INDICATION`, `HIGH` and mandatory human review. Inspect **Agents**, **State** and **Trace**, then record a human review, export a report and reload the saved run after restarting the app. Check all nine tabs and form scrolling at your actual Windows resolution.

Automated tests do not establish visual acceptance. Record the observed Windows/PyCharm results separately; a live Gemini call also requires its own validation.

Validation status and limitations: [docs/VALIDATION.md](docs/VALIDATION.md). Architecture and rules: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

V2 passed [GitHub Actions on Python 3.11 and 3.12](https://github.com/raquelquiterio2014-byte/firewatch-ai-lab/actions/runs/38488970214). V3 has **43 passing local tests**, including detection of changing repeated decisions, invalid citation/trace IDs, missed/extra review accounting, persistent trial links and CSV/JSON export. Remote CI must be checked for the V3 commit separately. These checks do not validate Windows GUI rendering or a live Gemini call.

Pilot metrics measure agreement with authored synthetic labels and consistency of identifiers/decisions. The baseline is simplified executable code, not measured human judgment. Human review time, field reliability and calibrated confidence are not measured.

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

- LangGraph Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph streaming: https://docs.langchain.com/oss/python/langgraph/streaming

- Gemini structured output: https://ai.google.dev/gemini-api/docs/generate-content/structured-output

This repository's scenarios contain no real incidents or measured sensor records. Synthetic agreement demonstrates consistency with project rules, not field accuracy.
