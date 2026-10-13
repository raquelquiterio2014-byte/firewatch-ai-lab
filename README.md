# FireWatch AI — V1

**Educational multi-agent prototype for fire-indicator analysis, evidence traceability and human review.**

Developed by **Raquel Cruz** as an educational project inspired by the evidence, critic and human-gate structure of ResilientCity AI. **Windows and PyCharm are the chosen environment for local execution and validation.**

FireWatch evaluates **supplied observations** about vegetation and the urban–vegetation interface. It distinguishes fire indications, contextual priority and evidence gaps. It does not independently diagnose a fire, forecast propagation, issue operational commands or establish that an area is safe.

## V1 — From a Form to a Traceable Workflow

This milestone adds readable component summaries in **Agents** and a typed completed-run snapshot in **State**, including human-review records. Package version: **1.1.0**. The earlier local V0 may differ from this repository. Download or clone the current version into a separate folder and open the project in PyCharm, preserving any previous local work.

## What is implemented

- English Tkinter/ttk desktop interface with scenarios and custom observations.
- Typed input and output models using Pydantic.
- Ten labelled synthetic scenarios and an evaluation screen.
- Planner, Evidence, Fire Assessment, Risk/Exposure, Decision, Critic and Reporter components.
- Deterministic Safety Gate and recorded human approval/rejection.
- SQLite run snapshots, evidence records, saved-run history and real JSONL trace events.
- TXT report and JSON run/evaluation export.
- Optional Gemini adapter with structured outputs, bounded retries and explicit fallback.
- Windows launcher and a GitHub Actions workflow.

## Two execution modes

**Deterministic:** works without an API key. It is a modular reference pipeline, not autonomous LLM reasoning. Rules are educational project hypotheses.

**Gemini hybrid:** Planner chooses one authorized analysis route, Decision drafts a structured review proposal, and Critic approves or requests revision. The selected route is executed and logged. Fire assessment, contextual priority, evidence checks and Safety Gate remain deterministic. At most one revision is allowed; each API call has at most two attempts with a 20-second request timeout. Missing credentials, provider/network failures or invalid output cause fallback and mandatory review.

`request_information_then_assess` records pending human information; it does not contact an external source and does not invent missing data. The application still analyzes the available observation with explicit unknowns.

The orchestrator is implemented in Python; **LangGraph is not yet integrated**. There is no camera, sensor ingestion, automatic contradiction extraction, MCP server, geospatial layer or live fire-data integration in this release.

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

### Local visual validation in PyCharm

Start with **Use Gemini (optional)** unchecked. Analyze **03 — Flames near people** and confirm `STRONG_INDICATION`, `HIGH` and mandatory human review. Inspect **Agents**, **State** and **Trace**, then record a human review, export a report and reload the saved run after restarting the app. Check all eight tabs and form scrolling at your actual Windows resolution.

Automated tests do not establish visual acceptance. Record the observed Windows/PyCharm results separately; a live Gemini call also requires its own validation.

Validation status and limitations: [docs/VALIDATION.md](docs/VALIDATION.md). Architecture and rules: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

V1 passed [GitHub Actions on Python 3.11 and 3.12](https://github.com/raquelquiterio2014-byte/firewatch-ai-lab/actions/runs/38325068591), including the 25-test suite and the ten-scenario deterministic evaluation. These checks do not validate Windows GUI rendering or a live Gemini call.

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

- Gemini structured output: https://ai.google.dev/gemini-api/docs/generate-content/structured-output

This repository's scenarios contain no real incidents or measured sensor records. Synthetic agreement demonstrates consistency with project rules, not field accuracy.
