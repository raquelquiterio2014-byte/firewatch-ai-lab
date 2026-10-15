# Validation record — FireWatch AI V1–V6

Updated 14 October 2026. [Windows acceptance evidence and exports](evidence/windows-2026-10-14/README.md) record the tests performed by Raquel Cruz and the files checked during the session. The GUI was executed on her Windows computer; automated development/CI tests use offline provider doubles.

**V1, V2, V3 and V4 were all tested and validated on Windows through Windows PowerShell by Raquel Cruz on 14 October 2026, within the basic acceptance scope documented below.** Python 3.12.10 was used. This session did not validate execution through PyCharm.

## Automated suites

| Milestone | Windows suite | Observed result |
|---|---:|---|
| V1 / 1.1.0 | 25 tests | OK; 10/10 synthetic evaluation |
| V2 / 2.0.0 | 35 tests | OK; 10/10 synthetic evaluation |
| V3 / 3.0.0 | 43 tests | OK; 10 cases × 2 deterministic trials |
| V4 / 4.0.0 initial snapshot | 63 tests | OK; missing-key fallback and live integration checked separately |

The subsequent V4 generateContent request-contract adjustment adds a regression test: **64 development tests passed** and [GitHub Actions passed on Python 3.11 and 3.12](https://github.com/raquelquiterio2014-byte/firewatch-ai-lab/actions/runs/38647508384) for commit `328bc4e109332ac6bdf79dda21dfa39d78e63346`. The 64-test suite was not rerun on the user's computer during this record; her local gateway file was updated and used for the successful live checks.

Checks include typed-input validation, unknowns, stale/future/conflicting evidence, bounded revisions, actual graph routes, trace IDs, edit invalidation, persistence, provider retry/error handling and review-request retention. Controlled failure/revision fixtures are offline tests, not live model behavior.

## Observed Windows acceptance

- V1: initial GUI; scenarios 01 and 03; approval recorded without clearing Safety Gate; approved run reloaded after restart.
- V2: direct and information-request branches; cards and workflow cleared after input editing; stale evidence requires review; evidence and executed route restored from history.
- V3: pilot dashboard; selected case 06 opens its saved analysis and shows `old` evidence; JSON/CSV exports; same pilot recovered after restart.
- V4: LLM tab and configured-key status; missing-key fallback with zero HTTP attempts; successful provider probe; three validated live agent responses for synthetic scenario 03; retained review reasons; same audit and Safety Gate recovered after restart; JSON/TXT exports.

## V3 export verification

The uploaded Windows JSON and CSV both contain ten cases, matching expected/actual/baseline fields and links to twenty unique trial run IDs. Metrics: system 10/10, simplified checklist 7/10, system missed/extra reviews 0/0, repeated decisions 10/10; recorded citation ID occurrences 30/30 and trace run IDs 20/20. The checklist is executable code, not measured human judgment.

## V4 live export verification

Run `948f6091-9bb4-405f-aec2-e5ecad377fc7`: synthetic scenario 03, hybrid mode `llm`, STRONG_INDICATION / HIGH / REQUIRED, no recorded errors. Planner, Decision and Critic each have source `gemini_api`, HTTP 200, one attempt and validated output. Decision/Critic review requests reach the deterministic Safety Gate. The Critic approved with zero revisions; no human approval was recorded for this V4 run.

The exported analysis validates against the Pydantic RunResult model (separate human-review records are removed before model validation). Every trace event and graph snapshot uses the exported run ID. The TXT matches the JSON report exactly after trimming outer whitespace. Evidence IDs refer to the supplied synthetic record.

An initial HTTP_400 was diagnosed locally as **invalid API key**. The gateway request format was adjusted during investigation, but the status persisted until a valid key was configured. Do not attribute the original failure solely to request format.

## Remaining scope and limitations

These checks establish a basic acceptance sequence on one Windows setup and one live Gemini synthetic scenario. They do not establish full layout acceptance across resolutions, execution from PyCharm, live Gemini agreement across all ten cases, adversarial live revision behavior, authenticated source truth, calibrated confidence or real-fire accuracy. The V4 deterministic pilot result was not separately supplied in this acceptance record; earlier V3 exports and automated CI evaluation remain distinct evidence.

The synthetic labels follow educational reference rules. Source/provenance and conflict flags are declarations. No real incidents, measured sensors, propagation forecasts or emergency actions were tested. V6 is now implemented; the independent real-cases project remains planned.

## V5 development verification — separate from Windows acceptance

The V5 implementation was checked in the development environment with Python 3.12: **92 automated tests passed**. These include the 64 prior regressions and 28 new tests for evidence-linked context, required review, legacy loading, explicit human judgments, disagreement/denominators, independent approval records, export links, cutoff filtering, unknown availability, partial updates, conflicting latest values, audit integrity and restart persistence. Provider transports remain mocked; Shadow Mode was verified offline.

The deterministic pilot retained system **10/10**, checklist **7/10** and repeatability **10/10**. The four-record synthetic shadow fixture was executed at UTC 12:00 and 13:00: the late report is excluded first and included later, changing NO_INDICATION / LOW / OPTIONAL to STRONG_INDICATION / HIGH / REQUIRED. The JSON fixture was imported separately. These demonstrations are project-rule consistency checks, not real-fire accuracy.

**V5 manual Windows acceptance by Raquel Cruz and V5 live Gemini validation are pending.** No actual human baseline dataset has been recorded during development; human assessment unit tests use explicitly identified fixtures. GUI-entered human judgments are marked output-seen. GitHub Actions now includes Windows Python 3.12 automated checks and a GUI construction/interaction smoke check, distinct from manual screen-layout acceptance. Follow [V5_WINDOWS.md](V5_WINDOWS.md) and record local evidence separately.

V5 [GitHub Actions run 38657345373](https://github.com/raquelquiterio2014-byte/firewatch-ai-lab/actions/runs/38657345373) completed successfully for commit `779161b0df6c0de8ea1b9bd29cda110c732b872a`, on Linux Python 3.11/3.12 and Windows Python 3.12, including the automated GUI smoke check. This does not establish manual acceptance on Raquel's computer.

## V6 development verification

**117 automated tests passed** in development: all 92 earlier regressions plus 25 V6 tests. New checks cover identical paired inputs/times, stable repetition inputs, unique IDs, offline/provider/fallback separation, proposal versus Safety-Gate differences, recorded HTTP/token/error metrics, missing components, cancellation, persistence, checksum/metric tampering, bad traces/citations, linked CSV/TXT exports, ZIP manifest integrity, original run/human record separation and CLI mode guards. Provider tests use offline fixtures or patched transports, not live requests.

The original synthetic pilot still matches 10/10 authored labels. The full offline paired comparison completed **20/20 agreeing pairs**, **40/40 intact runs**, **10/10 repeated cases**, and **zero provider attempts**. CLI report/CSV/JSON/bundle generation was checked separately. These results measure deterministic consistency and export integrity, not comparative Gemini performance or fire accuracy.

V6 Windows CI extends the automated smoke check to 12 tabs, comparison history, candidate-run opening, ZIP export and three window sizes. **Raquel's manual V6 Windows acceptance, V6 live Gemini comparison and an actual human baseline dataset remain pending.** The documented V4 live scenario remains separate historical evidence. Follow [V6_WINDOWS.md](V6_WINDOWS.md).

For reproduction, follow [V4_WINDOWS.md](V4_WINDOWS.md), [V3_WINDOWS.md](V3_WINDOWS.md) and [V2_WINDOWS.md](V2_WINDOWS.md). Keep provider-backed exports separate from mocked automated test results.
