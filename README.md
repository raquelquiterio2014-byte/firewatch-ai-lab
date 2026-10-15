# FireWatch AI — V6

**Educational multi-agent prototype for fire-indicator analysis, evidence traceability and human review.**

Developed by **Raquel Cruz** as an educational project inspired by the evidence, critic and human-gate structure of ResilientCity AI. **Windows and PyCharm are the chosen environment for local execution and validation.**

FireWatch evaluates **supplied observations** about vegetation and the urban–vegetation interface. It distinguishes fire indications, contextual priority and evidence gaps. It does not independently diagnose a fire, forecast propagation, issue operational commands or establish that an area is safe.

## Windows and PowerShell validation — V1, V2, V3 and V4

**All four versions (V1, V2, V3 and V4) were tested and validated by Raquel Cruz on Windows, using Windows PowerShell and Python 3.12.10, on 14 October 2026.** This refers to the recorded basic acceptance sequence: automated suites and the interface, workflow, review, export and persistence checks described in the [validation record](docs/VALIDATION.md). V4 also includes a successful live Gemini integration run for synthetic scenario 03.

This validation was performed through **PowerShell on Windows**; execution through PyCharm was not part of this session. Validation is limited to the recorded checks and synthetic observations, without a real-world fire accuracy claim. **V5 and V6 are implemented; Raquel's manual Windows acceptance and version-specific live-provider checks for these milestones remain pending.** V5's automated GitHub Actions checks passed on Linux and Windows, including basic GUI interactions.

## V6 — Comparative Evaluation and Evidence Bundles

Package version: **6.0.0**. V6 completes this implementation milestone for the synthetic laboratory, adding a dedicated **V6** tab while retaining context, human judgments, Shadow Mode, audited Gemini integration and the original pilot.

- **Paired evaluation:** the same frozen synthetic incident/time is analyzed by a deterministic reference and either a deterministic replay (offline default) or explicitly enabled Gemini hybrid. Select one case or all ten, with one to three trials per case. Each run has its own ID; repeated trials retain the same input hash/time.
- **Measured differences:** final Safety-Gate decisions, authored-label agreement, draft proposal differences, additional/removed review requests, actual modes, provider coverage, error codes, attempts, reported tokens, pipeline time, repeated decisions and trace/citation integrity. Hybrid assessment and priority remain deterministic; these comparisons do not measure independent LLM fire diagnosis.
- **Honest provider status:** successful, validated Planner/Decision/Critic audit records from `gemini_api` are required for a fully validated provider pair. Injected offline gateways and fallback are shown separately. An offline replay never appears as Gemini validation.
- **Portable evidence ZIP:** full comparison JSON, linked CSV, TXT report, original run snapshots, export-time human records, JSONL traces and a SHA-256 manifest. Checksums detect altered files; they do not authenticate source truth or reviewer identity.
- **Persistence and interruption:** comparisons reload from SQLite after restart. Progress is displayed after each pair. Stop takes effect after the current pair and saves an explicitly CANCELLED partial comparison. Unexpected failure may leave completed runs without a final comparison; history remains available.
- **Broader Windows automation:** CI exercises widgets, V5/V6 history, opening a compared run, bundles and layout refresh at three window sizes. Human readability and manual acceptance at your own resolution still require local checks.

Development verification: **117 automated tests passed**. The original pilot retains **10/10** synthetic matches. A full offline comparison completed **20/20 agreeing pairs**, **40/40 intact runs**, and **10/10 cases with stable repeated decisions**, with **zero provider attempts**. These are deterministic consistency results, not a real Gemini comparison or real-fire accuracy. [V6 Windows/PowerShell instructions](docs/V6_WINDOWS.md) include separate steps for actual provider validation.

The next research project will be the independent **FireWatch AI — Real Cases**, following ResilientCity AI — Real Cases. It will require sourced dossiers and retrospective availability records. No real-fire catalogue is included here.

## V5 — Context, Human Comparison and Shadow Mode

Package version: **5.0.0**. The V5 tab contains **Context**, **Human comparison** and **Shadow**. It adds:

- Ten optional evidence-linked variables: fuel type, vegetation density, slope, wind direction, gust speed, distances to people and infrastructure, people present, critical infrastructure and access status. Existing humidity, wind, temperature and vegetation inputs remain available. These are declared observations, not a propagation model.
- A deterministic Context component, executed within the Evidence node, with actual trace events, graph snapshots and report output. Unlinked entered context, inconsistent exposure declarations, and restricted access with fire indicators add mandatory review reasons. Core fire/priority rules and the ten reference labels remain unchanged.
- Explicit human judgments of assessment, priority and review requirement, stored separately from approval/rejection, checklist outputs and synthetic labels. The comparison uses the latest entry per reviewer for the selected run, preserves disagreement and exports linked JSON/CSV. **No entry means NOT_RECORDED**, not an invented human baseline. GUI entries are disclosed as output-seen, so they are not a blinded baseline.
- Offline retrospective **Shadow Mode**, importing normalized, timestamped records. Both observation time and declared availability time must be at or before the cutoff. Unknown availability and later records are excluded. Latest explicit values are selected per field; conflicting values tied at the latest observation time become unknown and require review. No eligible records means no run. Excluded free text never reaches analysis.
- SQLite history for shadow results, cutoff audits, field-to-evidence links and recorded human judgments. A fixed synthetic dataset is available in the interface and [examples/v5-shadow-synthetic.json](examples/v5-shadow-synthetic.json).

Development verification: **92 automated tests passed**, the deterministic pilot remains **10/10** with **7/10** checklist agreement and **10/10** repeatability, and the synthetic cutoff demo was executed. These are development results, not V5 Windows or field acceptance. Follow [V5 Windows/PowerShell checks](docs/V5_WINDOWS.md).

V5 introduced the offline research mechanism using synthetic demonstrations; no real-fire catalogue has been added. V6 now consolidates comparison and evidence exports, while the independent real-cases research remains a later project.

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
| V5 | Context output, entered human judgments/comparison and offline Shadow Mode with saved cutoff history |
| V6 | Paired comparison, actual execution modes, saved reports, cancellation and consolidated evidence ZIP |

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

Pilot metrics measure agreement with authored synthetic labels and consistency of identifiers/decisions. The pilot's checklist is simplified executable code, not measured human judgment. V5 human judgments are recorded separately and do not rewrite pilot metrics. Human review time, field reliability and calibrated confidence are not measured.

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
