# Windows acceptance evidence — 14 October 2026

Operator: Raquel Cruz. Windows PowerShell, Python 3.12.10, per-folder `.venv312` environments. Test counts and UI observations were supplied through console output and execution screenshots during the validation session. Exact display resolution and a full dependency lock were not recorded. This directory contains the original user-exported files; no credentials or request headers are included.

## Exported files

| File | Contents |
|---|---|
| [v3-pilot.json](v3-pilot.json) | V3 deterministic pilot, labels, metrics and 20 trial IDs |
| [v3-pilot.csv](v3-pilot.csv) | Ten per-case rows matching the JSON, including trial links |
| [v4-gemini-case03.json](v4-gemini-case03.json) | Live hybrid run, structured agent outputs, graph snapshots, trace, audit and Safety Gate |
| [v4-gemini-case03.txt](v4-gemini-case03.txt) | Readable report matching the JSON's report field |

V3 evaluation ID: `5b6f220b-f93f-4f55-8006-55cc5d34688f`. System 10/10; simplified checklist 7/10; missed/extra reviews 0/0; repeated decisions 10/10. The same evaluation ID and metrics were recovered after restart.

V4 run ID: `948f6091-9bb4-405f-aec2-e5ecad377fc7`, created 14 October at 19:31:56 America/Sao_Paulo (22:31:56 UTC). The incident is synthetic: smoke=yes, flames=yes, exposure=yes. Results: STRONG_INDICATION, HIGH, mandatory review, hybrid mode `llm`; no recorded errors or revisions. Planner/Decision/Critic each returned HTTP 200 with validated output on one attempt. Review requests from Decision and Critic remain in the Safety Gate. No human review was recorded for this run. The same call IDs, timestamps and safety reasons were restored after restart.

A separate configuration-only probe succeeded at 19:30:56 local time, HTTP 200 with validated JSON. Its audit was inspected in the session; it is not part of this run export. The initial HTTP_400 was diagnosed as an invalid API key, then resolved with a valid key. Credentials were entered through a masked local prompt.

## Code versions used

| Milestone | Repository snapshot | Windows tests |
|---|---|---:|
| V1 | `7b7158f6f98a5972e0e33746a05ec5c596fb2be6` | 25 |
| V2 | `3b0cf338a3632d6c7ed83b3e1038368177d4b628` | 35 |
| V3 | `e6344d120f055adeceef39817f6d5edac1813624` | 43 |
| V4 | `35aecc2d1d0bc916524315dd2f4dfc3d4e98c4f6`, then gateway.py replaced from `328bc4e109332ac6bdf79dda21dfa39d78e63346` | 63 before gateway update |

The updated repository suite has 64 tests and passed [CI on Python 3.11/3.12](https://github.com/raquelquiterio2014-byte/firewatch-ai-lab/actions/runs/38647508384). This is distinct from the 63-test Windows run. Package V4 remains 4.0.0; JSON `schema_version: 2.0` describes the saved-data format, not the application milestone.

Full observed scope and remaining checks: [VALIDATION.md](../../VALIDATION.md). The files prove a recorded synthetic integration run, not real-world fire accuracy or general live-model reliability. V5 and V6 remain deferred.
