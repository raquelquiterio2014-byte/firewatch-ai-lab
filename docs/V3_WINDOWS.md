# FireWatch AI — V3 Supervised Evaluation

V3 follows the ResilientCity progression from a traceable workflow to an inspectable evaluation dashboard. It evaluates **ten authored synthetic cases**, not real fires. The default pilot executes each case twice with the same incident snapshot and analysis time, saves all twenty runs and then saves a typed evaluation record.

## Run on Windows

Keep your V2 folder and data. Download the latest GitHub ZIP and extract V3 into a new folder. Open PowerShell in the folder containing `main.py`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

If locating the folder is difficult, paste this selector command into Windows PowerShell and choose the **V3 main.py** file in the extracted project:

```powershell
Add-Type -AssemblyName System.Windows.Forms; $fwV3File = New-Object System.Windows.Forms.OpenFileDialog; $fwV3File.Filter = "main.py|main.py"; if ($fwV3File.ShowDialog() -eq "OK") { Set-Location (Split-Path $fwV3File.FileName); py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt; .\.venv\Scripts\python.exe main.py }
```

No virtual-environment activation or execution-policy change is needed. The `run_gui.bat` launcher works after dependency installation.

## Evaluation tab

1. Click **Run pilot (10 cases × 2 trials)**. This protocol is deterministic and never activates Gemini, even if its checkbox is enabled elsewhere.
2. Expected summary: system matches **10/10**, checklist matches **7/10**, system missed/extra reviews **0/0**, repeated decisions **10/10**.
3. Scroll through all ten rows. Click a row to inspect expected/actual fields, baseline decisions, citation checks and trial run IDs.
4. Select case 06, the old observation. The system requires review; the simplified checklist does not. This illustrates an explicit rule difference.
5. Click **Open selected analysis** to load the first trial in Agents, Evidence, Workflow, State and Trace. The normal human-review controls can be used for that run.
6. Export JSON and CSV. JSON contains the protocol, metrics, labels and all trial IDs. CSV is a flat per-case comparison table.
7. Close and restart. Choose the saved evaluation from the pilot history and click **Load saved pilot**. Its counts and trial links should remain available.

The pilot record does not change when later human approvals/rejections are appended to its runs. Pilot metrics refer to the original automated outputs, not reviewer decisions. Human review time and reviewer agreement are not measured in V3.

## Metrics and limits

| Metric | What it checks | What it does not establish |
|---|---|---|
| System/checklist matches | First-trial agreement with authored assessment, priority and review labels | Accuracy in real fires or superiority over professionals |
| Field agreement | Separate counts for assessment, priority and required review | A calibrated probability |
| Missed/extra reviews | Differences from expected review labels | Operational false-negative/false-positive rates |
| Repeated decisions | Agreement of the three decision fields within repeated deterministic runs | Cross-machine, live-LLM or field reproducibility |
| Citation IDs | ID occurrences in Assessment, Risk and Proposal belonging to the first-trial input record | Truth, relevance or independent verification of evidence |
| Trace run IDs | Every recorded event in each completed trial referring to its own run | Completeness of every conceivable event |
| Mean pipeline time | Average run duration, including graph construction and execution | Human review time, database/export time or field response time |

Reference labels follow the same educational policy as the richer system, so this comparison is not an independent accuracy study. Citation counts include repeated use of the same record ID by different components. The default catalogue checks 30 citation occurrences and 20 trial traces.

## Checklist baseline

The baseline is **executable simplified checklist code**, not recorded human judgment. It assigns HIGH to reported flames, MEDIUM to smoke, LOW to explicitly absent indicators and UNDETERMINED otherwise. It requests review for indications or unknown smoke/flames/exposure. It does not adjust priority for exposure or inspect old/conflicting records. These omissions are intentional and documented, not claims about how professionals reason.

On the fixed catalogue, assessment agrees in 10/10 cases, priority in 8/10 and review in 9/10; all three fields together agree in 7/10. The richer system matches all three in 10/10 by construction of its authored test labels. Different cases or labels can change these counts.

## Evidence tab

The V3 inspector displays source, method, declared provenance, timestamp and flags in a table. Synthetic, reported and measured records remain distinct; measured is still declared metadata, not independent verification. COMPLETE refers only to known smoke, flames and exposure fields, not evidence truth.

This inspector can display multiple backend records, but the manual incident form still creates one evidence record per new analysis. Editing multiple records or extracting their text is not added in V3.

## Command-line validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --evaluate --repetitions 2 --output exports\v3-evaluation.json --csv exports\v3-evaluation.csv
```

43 local tests passed. The V3 UI and live Gemini have not been visually/provider-validated in the development environment. Verify all nine tabs, scrolling and exports at your actual Windows resolution. Use screenshots of real execution for portfolio evidence; conceptual posters are separate artwork.
