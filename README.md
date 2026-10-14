# FireWatch AI — V4

**Educational multi-agent prototype for fire-indicator analysis, evidence traceability and human review.**

Developed by **Raquel Cruz** as an educational project inspired by the evidence, critic and human-gate structure of ResilientCity AI. **Windows and PyCharm are the chosen environment for local execution and validation.**

FireWatch evaluates **supplied observations** about vegetation and the urban–vegetation interface. It distinguishes fire indications, contextual priority and evidence gaps. It does not independently diagnose a fire, forecast propagation, issue operational commands or establish that an area is safe.

## V4 — Audited Gemini Integration

Package version: **4.0.0**. V4 strengthens the optional Gemini workflow with explicit review booleans, retained escalation requests, a provider-only JSON probe and per-call audit records. Planner, Decision and Critic requests for human review survive revisions/rejected proposals and reach the deterministic Safety Gate.

The **LLM** tab shows model selection, key-configured status, the latest saved probe and the selected run's audit. **Test Gemini JSON** sends no incident observations; success verifies structured JSON access only. Calls record model, attempt outcomes, validation and provider-supplied token counts, without credentials or raw error bodies. The short labels **Review** and **Eval** keep all ten tabs accessible.

The V3 pilot remains deterministic, with ten synthetic cases, two trials per case, an executable checklist and saved comparison metrics. Its rule-based results do not validate live Gemini. Automated tests mock provider responses. On 14 October 2026, Raquel also completed a Windows acceptance sequence and a live Gemini analysis of synthetic scenario 03; the exported evidence is linked below.

Windows setup, protected key entry and actual live acceptance steps: [docs/V4_WINDOWS.md](docs/V4_WINDOWS.md). Preserve earlier folders/data before replacing your local project. Existing run snapshots remain readable; V4 adds a provider-check table and optional audit fields.

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
- Optional Gemini adapter with explicit review flags, audited structured outputs, bounded retries and explicit fallback.
- A configuration-only JSON probe, persisted separately from fire analysis.
- Windows launcher and a GitHub Actions workflow.

## Two execution modes

**Deterministic:** works without an API key. LangGraph runs rule-based specialist nodes; graph orchestration itself does not create autonomous LLM reasoning. Rules remain educational project hypotheses.

**Gemini hybrid:** Planner chooses one authorized analysis route, Decision drafts a structured review proposal, and Critic approves or requests revision. The selected route is executed and logged. Fire assessment, contextual priority, evidence checks and Safety Gate remain deterministic. At most one revision is allowed; each API call has at most two attempts with a 20-second request timeout. Missing credentials, provider/network failures or invalid output cause fallback and mandatory review. Requests for review are accumulated across calls and revisions; a later response cannot clear them.

`request_information_then_assess` records pending human information; it does not contact an external source and does not invent missing data. The application still analyzes the available observation with explicit unknowns.

The orchestrator uses **LangGraph 1.2.15**, pinned in requirements.txt. There is no camera, sensor ingestion, automatic contradiction extraction, MCP server, geospatial layer or live fire-data integration in this release.

## Run on Windows with PyCharm

Use Python 3.12 with Tkinter support for the documented Windows setup. CI also checks Python 3.11; compatibility with Python 3.13/3.14 has not been verified here. Download or clone the current repository, extract it if necessary, and open the folder containing `main.py` as a project in PyCharm. Run the following commands in the PyCharm terminal from that project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

After creating the environment, configure the PyCharm project interpreter to use `.venv\Scripts\python.exe`. Run `main.py` with the working directory set to the project folder, so `data/` and exports are created in the intended location.

Alternatively, after installing requirements, double-click `run_gui.bat`. It uses the local `.venv` if present, otherwise the Windows Python launcher.

No activation or PowerShell execution-policy change is required. On Linux, install the distribution's Tkinter package if it is absent.

### Optional Gemini

Set the key in the same terminal before launching. The app reads environment variables; it **does not automatically load `.env`**. Use the masked PowerShell entry in [V4_WINDOWS.md](docs/V4_WINDOWS.md), so the credential is not entered as literal command history.

```powershell
$env:GEMINI_MODEL = "gemini-2.5-flash"
.\.venv\Scripts\python.exe main.py
```

First use the **LLM** tab and **Test Gemini JSON** with a configured key, then select **Use Gemini (optional)** in the Incident tab for a synthetic analysis. Model availability and structured-output support depend on the provider/account. Do not put a real key in source files or commits. The default model is configurable. The recorded Windows scenario-03 run used gemini-2.5-flash; that single run does not validate all scenarios or future provider availability.

## Interface

| Tab | Purpose |
|---|---|
| Incident | Scenario selector, normalized observations, source/provenance and saved-run history |
| Agents | Actual component results, selected plan, critic verdict and revision count |
| Workflow | Compiled node topology, visited route and live completion updates |
| Evidence | Source/provenance inspector plus descriptive completeness, timestamps and flagged conflicts |
| Review | Mandatory reasons, retained LLM review requests and reviewer/comment records |
| Report | Explainable TXT report and JSON export |
| Trace | Actual events linked to the current run ID |
| State | Intermediate graph snapshots during execution; validated final outputs and human reviews afterward |
| Eval | Saved pilot dashboard, baseline comparison, repeated trials, per-case inspection and JSON/CSV export |
| LLM | Requested model, key-configured status, provider JSON probe and per-call audit |

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

### Local visual validation on Windows / PyCharm

Start with **Use Gemini (optional)** unchecked. Analyze **03 — Flames near people** and confirm `STRONG_INDICATION`, `HIGH` and mandatory human review. Inspect **Agents**, **State**, **LLM** and **Trace**, then record a human review, export a report and reload the saved run after restarting the app. Check all ten tabs and form scrolling at your actual Windows resolution.

Automated tests do not establish visual acceptance. Record the observed Windows/PyCharm results separately; a live Gemini call also requires its own validation.

Validation status and limitations: [docs/VALIDATION.md](docs/VALIDATION.md). Architecture and rules: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Recorded Windows validation, 14 October 2026:** V1/V2/V3/V4 suites passed 25/35/43/63 tests respectively. The subsequent V4 request-contract fix passes **64 tests** and [GitHub Actions on Python 3.11 and 3.12](https://github.com/raquelquiterio2014-byte/firewatch-ai-lab/actions/runs/38647508384). Separately, the exported live Gemini run confirms validated Planner, Decision and Critic calls, STRONG_INDICATION / HIGH / REQUIRED, retained review requests, and reload after restart. See [the acceptance record and JSON/TXT/CSV evidence](docs/evidence/windows-2026-10-14/README.md). This is a limited synthetic acceptance sequence, not full visual acceptance across resolutions or field validation.

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

- Gemini GenerateContent API: https://ai.google.dev/api/generate-content
- Gemini structured output: https://ai.google.dev/gemini-api/docs/generate-content/structured-output

This repository's scenarios contain no real incidents or measured sensor records. Synthetic agreement demonstrates consistency with project rules, not field accuracy.
