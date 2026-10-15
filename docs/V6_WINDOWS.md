# V6 — Windows PowerShell acceptance

Version: **6.0.0**. Synthetic laboratory implementation milestone completed; **Raquel's manual V6 Windows acceptance and V6 live Gemini comparison remain pending**. Earlier V1–V4 evidence remains historical and separate. V5 automated CI passed; that does not replace manual V5/V6 acceptance.

## Install separately

The named ZIP contains `FireWatch-V6`. Place that folder in `D:\`, keep earlier version folders, and use PowerShell:

```powershell
Set-Location "D:\FireWatch-V6"
Test-Path .\main.py
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
.\.venv312\Scripts\python.exe -c "from firewatch import __version__; print('FireWatch AI:', __version__)"
.\.venv312\Scripts\python.exe -m unittest discover -s tests -v
.\.venv312\Scripts\python.exe main.py
```

Confirm `Test-Path` is **True** before continuing; otherwise enter the nested folder containing `main.py`. Expect **6.0.0** and **117 tests / OK**. No activation or policy change is needed. The launcher still prefers `.venv312`, then `.venv`, then Python 3.12.

## First comparison — no API key required

1. In the **V6** tab, choose **03 — Flames near people**, two trials, and leave **Candidate uses Gemini** unchecked. Click **Run paired comparison**. Expect COMPLETE, deterministic_replay, 2/2 final agreement, 0/2 validated provider pairs and 4/4 intact runs.
2. Select a row and click **Open candidate run**. Inspect STRONG_INDICATION / HIGH / REQUIRED, Context, Report, Trace and State. These are deterministic results.
3. Back in V6, export JSON, CSV, TXT and **Evidence ZIP**. The ZIP includes `comparison.json`, `comparison.csv`, `report.txt`, numbered `runs/*.json`, `trace.jsonl` and `manifest.json`. Run IDs and input hashes link all files. Human approvals and judgments reflect export time and do not alter the original Safety Gate.
4. Choose all ten cases with two trials. Expect 20 paired trials, 40 saved runs, 20/20 agreement and 10/10 repeatable cases. Zero HTTP attempts is correct for offline replay. This is not a live model benchmark.
5. Restart the app and **Load comparison** from its history. Verify the same ID, modes, decisions, run links and exports. Existing runs, pilot evaluations, human records and shadow analyses remain readable.
6. Check all **12 main tabs**, V5's three sub-tabs, scrolling and table navigation at your screen resolution. Editing incident input must invalidate current analysis without mislabeling saved comparison or shadow records.

CLI equivalent:

```powershell
.\.venv312\Scripts\python.exe main.py --compare --repetitions 2 --output exports\v6-comparison.json --csv exports\v6-comparison.csv --report exports\v6-report.txt --bundle exports\v6-evidence.zip
Invoke-Item .\exports
```

CLI prints summary metrics; full run snapshots are in the output JSON, ZIP and SQLite. `--compare-cases 3` selects a small initial comparison. The original `--evaluate` pilot remains separate with 2–5 trials; comparative evaluation supports 1–3 trials.

## Optional actual Gemini comparison

Configure the key in the **same launching PowerShell process**, using the masked procedure in [V4_WINDOWS.md](V4_WINDOWS.md). Credentials are environment-only; `.env` is not loaded. Start the app, verify **LLM → Test Gemini JSON**, then choose scenario 03, **one trial** in V6, and explicitly check **Candidate uses Gemini**.

This sends synthetic observations to the provider. It can make up to **five agent calls / ten HTTP attempts per pair** if a revision and retries occur. All ten cases × two trials therefore allow up to 100 agent calls / 200 HTTP attempts. Actual counts are reported, and provider quota/time constraints still apply. Start with one case.

Inspect requested versus actual mode, all call audits and retained human-review requests. A complete provider-backed pair requires validated Planner, Decision and Critic calls, all from `gemini_api`. Extra human review can legitimately differ from deterministic labels; final assessment/priority remain rule-based in this hybrid design. Failed calls trigger fallback rather than being reported as successful Gemini execution.

CLI equivalent, after configuring the environment:

```powershell
.\.venv312\Scripts\python.exe main.py --compare --compare-cases 3 --repetitions 1 --llm --model gemini-2.5-flash --output exports\v6-gemini-case03.json --bundle exports\v6-gemini-case03.zip
```

Exit code 0 means the requested complete run passed integrity checks and, when hybrid is requested, all pairs met provider-audit criteria. Code 1 indicates integrity or removed-review issues; code 2 indicates that requested provider coverage was incomplete (including fallback). It does not imply field accuracy or exact authored-label agreement.

## Stop and persistence

**Stop after current pair** does not interrupt an in-flight request. It finishes the current pair, then saves CANCELLED with the completed pairs and their own denominator. A single trial never counts as a repeated-decision check. Closing the app or an unexpected failure may leave saved runs without a finished comparison; do not infer a completed report from those runs.

Record date, Python version, screenshots, observed metrics, exported IDs and live/offline mode separately. Automated Windows smoke checks refresh three sizes but do not prove that every control is readable or unclipped. Manual V6 acceptance and live Gemini evidence must be documented after actual execution.
