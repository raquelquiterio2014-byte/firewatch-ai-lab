# FireWatch AI — V4 Audited Gemini Integration

V4 strengthens the optional hybrid mode with a provider JSON probe, per-call audit and persistent human-review requests. The code/tests are ready; **real Gemini access and Windows UI acceptance are still local validation steps**. The automated suite uses mocked transports and injected gateways.

## What changed

- The **LLM** tab shows requested model, key-configured status, latest saved probe and calls from the selected run. It does not display or export the key value.
- **Test Gemini JSON** sends a configuration-only prompt and validates `{ "status": "ok" }`. It sends no incident observations and does not validate fire analysis.
- Planner, Decision and Critic return an explicit `human_review` boolean. Schema omissions or malformed responses cause fallback.
- Review requests are accumulated across agent calls/revisions, passed to Safety Gate, and retained in State, reports and exports. A rejected proposal's valid review flag is not erased by a later revision.
- Calls record requested/reported model, attempts, HTTP outcome, structured validation and token counts when supplied by the provider. No raw provider error body, request headers or credentials are stored.
- At most two attempts per call; retry only transient HTTP/network failures. Invalid output, explicit provider blocks/truncation and non-transient errors are not retried.
- The deterministic pilot stays separate: pressing **Run pilot** does not call Gemini.

The short tab labels are now **Review** and **Eval** to keep all ten tabs accessible in narrower windows.

## Install and run

Download the current GitHub ZIP into a new folder, preserving V3 and its data. Open PowerShell in the folder containing `main.py`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

The same `.venv` interpreter can be configured in PyCharm, with the project folder as working directory. No virtual-environment activation or execution-policy change is needed.

## Configure Gemini in PowerShell

Close the app first. Use the following commands in the terminal that will launch it. The key is entered through a masked prompt, not as literal command text. Do not paste the key into chat, source files, screenshots or exports.

```powershell
$fwV4Secret = Read-Host "Gemini API key" -AsSecureString
$fwV4Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($fwV4Secret)
try { $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($fwV4Pointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($fwV4Pointer) }
$env:GEMINI_MODEL = "gemini-2.5-flash"
.\.venv\Scripts\python.exe main.py
```

The app reads environment variables from the launching process. It does not load `.env`. Closing the terminal ends this session configuration. The model can also be edited in the LLM tab; key configuration requires relaunching from the configured terminal.

## Local acceptance sequence

1. Without a key, use deterministic mode and run the synthetic pilot. Expect system 10/10, checklist 7/10, repeated decisions 10/10.
2. Still without a key, enable Gemini and Analyze Incident. Expect FALLBACK, mandatory human review and `MISSING_KEY` with zero HTTP attempts in the LLM audit.
3. Configure the key and relaunch. In LLM, check key-configured YES and the intended model. Click **Test Gemini JSON** once. Success means structured JSON access was verified at that moment only.
4. If the probe reports HTTP_429, stop retrying manually and check provider quota/availability. HTTP_400/401/403/404 should be investigated as request, credential, permission or model issues; they are not automatically retried.
5. For the first live analysis, use a synthetic scenario. Enable Gemini and Analyze Incident. Verify mode LLM, audit source `gemini_api`, validated Planner/Decision/Critic outputs and no fallback. A call can still fail after a successful probe.
6. Inspect Review and State: any LLM human-review request must be reflected in the Safety Gate. Mandatory deterministic review reasons must also remain intact. The model is not required to request an extra review in every scenario.
7. Export run JSON and TXT report, restart, and load the run. The audit and retained review requests must survive. Keep these files as live integration evidence, separate from mocked automated tests.
8. Inspect all ten tabs and scrolling at the actual Windows resolution. Record command, versions, selected model, scenario, observed mode, audit outcomes and date.

The revision/escalation adversarial cases are tested with controlled doubles. Do not assume the live model will naturally produce those exact responses during a manual check.

## CLI probe and hybrid scenario

### JSON request compatibility fix (14 October 2026)

The initial V4 local connection probe returned HTTP_400 despite a configured key.
The adapter now uses `generationConfig.responseMimeType` and
`generationConfig.responseJsonSchema` for the `generateContent` endpoint instead
of the newer `responseFormat` envelope. This targets the Gemini 2.5 REST contract;
the HTTP status alone does not establish the original provider error's exact cause.
The corrected request contract is covered by offline tests (64 tests total).
Live success remains pending a new local probe. A configured key is not proof of
valid credentials, available quota or model access.

Existing V4 folders can replace only `firewatch/gateway.py` from the corrected
repository, after closing the app and backing up that file. Dependencies, saved
runs and key configuration do not change. Relaunch from the same configured
PowerShell session and click **Test Gemini JSON** once before incident analysis.

After environment configuration:

```powershell
.\.venv\Scripts\python.exe main.py --check-gemini --output exports\gemini-probe.json
.\.venv\Scripts\python.exe main.py --scenario 3 --llm --output exports\v4-hybrid-case.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The probe returns exit code 0 on success or 2 on failure. It persists its audit in SQLite. It is separate from `--evaluate` and cannot be combined with a scenario or pilot. A scenario can use `--model MODEL_NAME` as an override.

## Interpreting audit fields

`gemini_api` identifies the built-in provider adapter; check `succeeded`, `output_validated` and the attempt list to determine whether access succeeded. Missing key has zero attempts. `injected_gateway` identifies a caller-supplied gateway, used by offline agent fixtures; it is not proof of Gemini access. `configuration` records failure before a gateway was initialized.

Requested model and provider-reported version are distinct. Token counts are recorded only when returned, not estimated; this app does not calculate billing cost. The probe contains no incident observations. Live analysis sends the supplied observation context to Gemini.

Successful API parsing does not establish calibrated reasoning, source truth or fire accuracy. V4 retains the synthetic research scope, reference rules and deterministic human gate. Live data, human-baseline collection and retrospective cutoff/shadow mode remain later milestones.

## Validation status

63 local automated tests pass, including mocked full HTTP flow, retry limits, invalid/truncated output, explicit review flags, secret-free audit fields, persistence and escalation across rejected/revised proposals. **No live Gemini invocation was made during this implementation.** Windows visual inspection is also pending.

Official API reference consulted: https://ai.google.dev/api/generate-content
