# FireWatch AI — V2 on Windows

## What changed from V1

- LangGraph conditional Planner route and bounded Critic revision.
- Workflow tab with node topology and actual visited route.
- Intermediate state snapshots shown while the analysis runs and persisted with completed runs.
- Descriptive Evidence Quality: known fields, provenance declarations, timestamps and conflict flags.
- Editing inputs clears stale displayed results; saved runs remain in history.
- Package version 2.0.0; old V1 saved runs remain readable.

## Install and run

Download the latest repository ZIP and extract it into a new folder, keeping your V1 folder intact. The project folder is the one containing `main.py` and `requirements.txt`.

Open PowerShell, then use your actual extracted path:

```powershell
cd "D:\YOUR_FOLDER\firewatch-ai-lab-main"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

No virtual-environment activation or execution-policy change is needed. A reused environment must also install the updated requirements because V2 adds LangGraph. The launcher does not install dependencies automatically.

## Minimum visual validation

1. Leave Use Gemini unchecked. Select scenario 01 and Analyze Incident. Expect NO_INDICATION / LOW / OPTIONAL. Workflow must skip Information Request.
2. Select scenario 02. Cards must clear before reanalysis. Analyze: expect POSSIBLE_FIRE / UNDETERMINED / REQUIRED. Workflow must include Information Request; Evidence shows PARTIAL indicator completeness.
3. Scenario 03: expect STRONG_INDICATION / HIGH / REQUIRED. COMPLETE refers only to three known indicator fields; it is not confidence or verified diagnosis.
4. Scenarios 05 and 06: confirm conflict and old-evidence flags. They require review even if another field appears reassuring.
5. Inspect Workflow: green means previously visited and amber means last completed. Scroll inside the diagram to reach the final nodes. State is provisional while running and final afterward.
6. Edit any input after a completed analysis: cards must say NOT ANALYZED / ANALYSIS NEEDED / PENDING until analysis runs again. The old result must remain available in history.
7. Record approval with reviewer/comment. Safety reasons must remain unchanged. Export JSON and confirm graph_steps and evidence_quality are included.
8. Restart and load the saved run; review records and executed graph route must be restored.
9. Run Evaluation: expect 10/10 reference labels. This is synthetic agreement, not field accuracy.

Most deterministic runs finish too quickly to observe each live update individually. Their intermediate states are retained in the exported JSON. Deliberate Critic rejection is covered by mocked automated tests; the standard deterministic catalogue does not claim to exercise that branch.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --evaluate --output exports\v2-evaluation.json
```

35 local tests passed with LangGraph 1.2.15 and Pydantic 2.14.1. No live Gemini invocation or V2 visual rendering was validated in the development environment. Record actual Windows screenshots, resolution, scenario and result when you complete the checks.

## Reading the evolution honestly

V1 introduced readable components and completed Shared State. V2 changes the coordinator to an executed graph, exposes conditional branching and intermediate state, and improves uncertainty presentation. It does not add sensors, satellite ingestion, real-fire validation, propagation prediction, checkpoint resume or automatic emergency actions.
