# Validation record — 12 October 2026

## V1 increment

Package 1.1.0 adds a readable Agents view and a typed completed-run State view. The local suite has **25 passing tests**, including three new checks for preservation of unknowns, separation of snapshot copies and retention of Safety Gate reasons after human approval. The original backend passed remote CI on Python 3.11 and 3.12: https://github.com/raquelquiterio2014-byte/firewatch-ai-lab/actions/runs/38315261731. V1 GUI rendering still requires Windows inspection.

## Automated checks

The development environment uses Python 3.12 and Pydantic 2.13.5. Run `python -m unittest discover -s tests -v` and `python main.py --evaluate` to reproduce the checks.

Initial automated suite: **22 tests passed**. Deterministic synthetic catalogue: **10/10 labelled scenarios matched the reference expectations** for assessment, priority and mandatory human review.

Tests include invalid humidity/negative wind/non-finite values, timezone and duplicate-ID validation, unknown inputs, stale/future/conflicting evidence, unchanged safety requirements, fabricated citations, bounded critic revision, mocked timeout/invalid schema, safe error logging, persistence and worker-thread database operations.

The recorded CLI catalogue output is in [evaluation_result.json](evaluation_result.json), with expected/actual fields and run IDs.

Optional Gemini logic and REST parsing are tested using offline doubles. **No live Gemini call has been made.** This does not validate the selected model's current availability or provider compatibility.

## Visual verification still required

Tkinter is importable in the development environment, but a graphical display is unavailable. No screenshot of an executed GUI is supplied and no visual acceptance claim is made.

On Windows:

1. Launch `run_gui.bat` or `python main.py`.
2. Inspect at 1366×768 and a larger resolution; resize to the minimum supported window. Confirm form scrolling, readable cards and access to all eight tabs.
3. Run scenario 03. Expect STRONG_INDICATION, HIGH and REQUIRED human review.
4. Run scenario 01. Expect NO_INDICATION, LOW and OPTIONAL review; confirm the report does not claim safety.
5. Enter humidity 101 or negative wind. Confirm input is rejected before analysis.
6. Run Evaluation and confirm 10/10 labels, then export its JSON.
7. Record approval/rejection with reviewer and comment. Confirm the record appears and original Safety Gate reasons remain.
8. Export TXT and JSON, close the app, relaunch and load the same saved run.
9. Without a key, explicitly enable Gemini: expect FALLBACK and REQUIRED review.

Record actual resolution, command, dependency versions, scenario, observed result and date. Add screenshots only from an actual run and label them with the tested version. Do not use design mockups as execution evidence.

## Evaluation limits

The catalogue and expected labels were authored from educational reference rules. It contains no real sensor input or field validation. The GUI's source/provenance and conflict flags are declared metadata. This version is not an independently validated fire-detection or emergency-response system.

GitHub workflow source is included. Remote CI status must be checked after publication; it has not been assumed from local results.
