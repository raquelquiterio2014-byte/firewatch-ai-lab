# V5 — Windows PowerShell acceptance

Version: **5.0.0**. Status: development tests passed; **Raquel's local V5 Windows acceptance is pending**. V1–V4's recorded acceptance is preserved separately. No V5 live Gemini run is claimed.

## Install in a separate folder

Keep the V1–V4 folders intact. Extract the V5 download into `D:\FireWatch-V5` and enter the actual directory containing `main.py`, which may be nested inside the extraction folder. In PowerShell:

```powershell
Set-Location "D:\FireWatch-V5"
Test-Path .\main.py
```

Continue only when `True` appears. If it is false, use `Get-ChildItem` to find the nested project directory and enter it. Then:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
.\.venv312\Scripts\python.exe -c "from firewatch import __version__; print('FireWatch AI:', __version__)"
.\.venv312\Scripts\python.exe -m unittest discover -s tests -v
.\.venv312\Scripts\python.exe main.py
```

Expect **5.0.0** and **92 tests / OK**. No activation or execution-policy change is needed. `run_gui.bat` prefers `.venv312`, then `.venv`, then `py -3.12`. Close the GUI before starting another instance.

## Acceptance sequence

1. Keep **Use Gemini (optional)** unchecked. Run the existing deterministic pilot in **Eval**: expect 10/10 system matches, 7/10 checklist matches and 10/10 repeated decisions. Export JSON/CSV.
2. Select scenario 01. Scroll down the Incident form to V5 context. Enter fuel `grass`, slope `15`, gust `40`; keep people/infrastructure/access unknown. Analyze. Expect NO_INDICATION / LOW / OPTIONAL: dry/environmental context does not prove fire. In **V5 → Context**, inspect values and evidence IDs; inspect the Context event in Trace and context output in State/Report.
3. With scenario 01's exposure still `no`, set people present to `yes`, analyze again. Expect NO_INDICATION / LOW with **REQUIRED** review and an exposure inconsistency reason. No field is silently corrected.
4. Under **V5 → Human comparison**, enter your name, an explicit assessment, priority, review judgment and rationale. The app does not prefill reference answers. Record it, export JSON/CSV, and verify disagreement if you intentionally enter different values. This GUI comparison is marked output-seen, not blinded. It does not approve the run or clear Safety Gate.
5. Under **V5 → Shadow**, click **Load synthetic demo**. Cutoff `2026-10-14T12:00:00Z`; click **Run Shadow (offline)**. Inspect the result/audit: `demo-early` and `demo-context` included; late report and unknown-availability record excluded; NO_INDICATION / LOW / OPTIONAL. No provider call is made.
6. Change the cutoff to `2026-10-14T13:00:00Z` and run again. `demo-late` now joins the projection; expect STRONG_INDICATION / HIGH / REQUIRED. IDs must differ from the first run. Export shadow JSON/TXT for both cutoffs. UTC 12:00 corresponds to 09:00 in São Paulo on this date.
7. Try a cutoff earlier than all observations: the operation must fail without saving a fabricated analysis. A cutoff without a timezone is also rejected.
8. Restart the app. Load the previously reviewed run through Incident history and verify its human comparison. In V5/Shadow load each saved shadow from its own history and verify the stored cutoff and decisions. Earlier run snapshots remain immutable.
9. Check form scrolling, all 11 main tabs and the three V5 sub-tabs at your actual screen resolution. Editing input must clear current analysis cards/context/comparison until reanalysis or history load. Saved shadow results retain their explicitly displayed original cutoff.

## CLI reproduction

```powershell
.\.venv312\Scripts\python.exe main.py --evaluate --output exports\v5-pilot.json --csv exports\v5-pilot.csv
.\.venv312\Scripts\python.exe main.py --shadow-demo --cutoff "2026-10-14T12:00:00Z" --output exports\v5-shadow-12h.json
.\.venv312\Scripts\python.exe main.py --shadow-demo --cutoff "2026-10-14T13:00:00Z" --output exports\v5-shadow-13h.json
.\.venv312\Scripts\python.exe main.py --shadow examples\v5-shadow-synthetic.json --cutoff "2026-10-14T12:00:00Z" --output exports\v5-shadow-import.json
```

Exports are created relative to the working directory; open it using `Invoke-Item .\exports`. CLI and GUI use `data/` unless `--data-dir` is supplied. Shadow Mode rejects `--llm` explicitly.

## Data interpretation

Each dataset record has `evidence` (observed time, source/content/provenance), declared `available_at`, and manually normalized `values`. Omitted value fields are not updates; explicitly entered `unknown`/`null` values reset that field to unknown. Do not export a partial dataset with defaults filled in: use `model_dump_json(exclude_unset=True)` when generating JSON from these models. Availability is self-reported and is not authenticated. There is no automatic extraction from free text and no real-fire source research in this release.

Archive results with date, Python version and observed Windows outcomes. Synthetic agreement and offline fixtures do not establish real-world fire accuracy, a blinded human baseline or live Gemini validation for V5.
