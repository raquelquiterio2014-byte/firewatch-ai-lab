# FireWatch AI — V5 Architecture

## Dependent state and real branches

The `Pipeline` builds a LangGraph `StateGraph(WorkflowState)` for each run. The graph state is a TypedDict containing Pydantic-validated incident and specialist outputs. Every node returns updates consumed by later nodes. RunResult validates the finished output, including provenance, Safety Gate, revisions, trace and graph-step snapshots.

```mermaid
flowchart TD
    E[Evidence checks and quality] --> P[Planner]
    P -->|Direct route| A[Fire assessment]
    P -->|Information needed| I[Record human information request]
    I --> A
    A --> R[Risk and exposure]
    R --> D[Decision proposal]
    D --> C{Critic}
    C -->|First rejection| V[Increment revision count]
    V --> D
    C -->|Approved or revision exhausted| S[Safety Gate]
    S --> F[Explainable report]
    F --> H[Pending or optional human review]
```

The Planner route selects whether the information-request node executes. It does not contact external sources or fill unknown fields. The Critic route executes Decision again only after the first rejection. A second rejection proceeds to Safety Gate with mandatory human review. Recursion limit 30 is an additional guard; the application enforces at most one revision independently.

`docs/workflow.mmd` is produced by the same compiled graph factory used for execution. The GUI renders its corresponding topology and highlights visited nodes. The route displayed below it comes from actual LangGraph stream updates, never a hard-coded list of claimed calls.

## Rule-based and LLM responsibilities

In deterministic mode, nodes use educational rules. In hybrid mode, Planner, Decision and Critic may call the Gemini adapter. Evidence, Fire Assessment, Risk/Exposure, Safety Gate and Reporter remain deterministic. LangGraph does not itself make these components LLM agents.

The deterministic Critic checks classification, contextual priority, citations and review requirements before the optional LLM Critic. Rejected proposals remain visibly unapproved after the limit. Reference assessment and contextual priority are retained; Safety Gate cannot be overridden by a proposal or later human-review record.

The gateway retains environment-only credentials, at most two attempts per call, timeout, structured validation and explicit fallback. The default mode does not call an external API. V4 has recorded live Gemini evidence for one synthetic scenario; V5-specific live acceptance remains pending. Automated provider parsing and agent behavior are tested with offline doubles.

## V5 context, human judgments and retrospective projection

`FireContext` adds optional normalized context and `Incident.context_evidence_ids` links it to supplied records. The Context component executes inside the graph's Evidence node and emits actual trace events. Its `ContextResult` is consumed by Decision and the deterministic Safety Gate, exported in the report and retained in graph/final state. It does not modify the core assessment or priority rules. Unknown optional context alone does not add escalation; entered unlinked context, exposure inconsistencies and restricted access alongside fire indicators do.

`HumanAssessment` is separate from `HumanReview` and `PilotEvaluation`. It requires explicit assessment/priority/review judgments, reviewer, rationale and an output-seen flag. SQLite retains append-only assessment entries. Comparisons select the latest entry per reviewer for one saved run, with entry/reviewer counts rather than a claim of independent scenario accuracy. GUI entries are always output-seen. Approval does not supply a baseline judgment and neither record alters the saved Safety Gate.

`ShadowDataset` contains manually normalized partial field updates with evidence observation times and declared availability times. Projection requires both times <= cutoff; missing availability and later observations are excluded. It applies the latest observation time per explicitly supplied field. An explicit unknown overwrites an earlier known value; omitted fields do not. Different values tied at the latest observation time become unknown and flag conflicts. Core and context values retain field-to-evidence links. The input location/environment are static dataset metadata, not time-varying observations.

Only eligible evidence content and projected values enter a deterministic Pipeline at the cutoff time. No provider is invoked. The exclusion audit contains IDs/reasons, never the excluded content or normalized values. No eligible records means analysis is blocked. `ShadowAnalysis.executed_at` records the actual execution time; its run `created_at` is the historical analysis cutoff. A ShadowPolicy trace event records filtering and its field links. The cutoff is a retrospective analysis reference, not a claim that the software ran at that historical time.

Shadow run and audit snapshots are saved together in one SQLite transaction; JSONL is appended afterward. Immutable shadow history and separate JSON/TXT exports remain available after restart. `ShadowAnalysis` checks that mode is deterministic, cutoff matches analysis time, and run evidence IDs match the inclusion audit. Existing V1–V4 snapshots load with empty/default context fields and no old snapshot is rewritten.

This implementation prepares a research workflow with synthetic demonstrations. Source availability declarations are not authenticated, and no real-case dossiers, sensor stream or operational decision system have been added.

## Evidence quality

`EvidenceQuality` reports known/unknown smoke, flames and exposure fields, stale/future record IDs, manually flagged conflicts and counts of declared provenance types. COMPLETE means only that those three indicator fields are known. It does not mean evidence is correct, current, independent or sufficient for an operational decision. No confidence score or calibrated probability is computed.

The six-hour stale policy and five-minute future-time tolerance are demonstration choices. Weather and vegetation inputs are preserved context, not a fire-spread model. Source/provenance and conflict flags are declared metadata. Normalized fields drive rules; free text is not automatically extracted or reconciled.

## Streaming and persistence

LangGraph streams node updates. The coordinator creates detached `GraphStep` snapshots after each completed node, logs actual events and optionally calls an observer. GUI workers send updates through a queue; only the Tk thread updates widgets.

The live State view is provisional. Only a completed RunResult is saved in SQLite; intermediate snapshots are stored inside that completed result. There is no LangGraph checkpointer, pause/resume checkpoint or crash recovery for unfinished analyses. Human Gate records a pending requirement, while the user's later review is appended separately through SQLite. It is not a LangGraph interrupt.

SQLite's run snapshot remains authoritative. Incident/evidence tables provide convenient lookup; editing an observation does not rewrite older run snapshots. Human reviewer identity is self-reported. Database operations create, commit and close their own connections in the calling thread.

JSONL is an additional export after database commit. If file writing fails, the run may already exist in SQLite; check saved-run history first. V1 snapshots load with default empty graph steps and no quality summary. `reference_pipeline.py` preserves the V1 coordinator for regression comparison.

## Input/result separation

Editing the form invalidates current cards, report and review controls until another analysis or history load. If edits occur while a job is running, the completed earlier input is saved but not presented as a result for the edited form. Preset selection changes the input; reanalysis is always needed. Existing saved runs remain accessible through history.

## V3 supervised evaluation

`PilotEvaluation`, `EvaluationCase`, `EvaluationTrial` and `EvaluationMetrics` validate the comparison record. The evaluation function creates each synthetic input once and freezes its analysis time for two to five deterministic trials. It compares first-trial outputs with authored labels and a separate executable checklist, then compares repeated decision fields with each other. It does not invoke Gemini.

The protocol saves every trial RunResult and then its completed PilotEvaluation in SQLite. If evaluation is interrupted, completed trial runs may exist without a final pilot record. There is no evaluation resume/checkpointer. Later human reviews are separate records and do not retroactively modify the saved evaluation metrics. The new table is created alongside existing tables, without rewriting V1/V2 run snapshots.

The GUI uses the existing worker/queue pattern for evaluation. Summary cards and per-case rows are derived from stored typed data. CSV exports flattened comparisons and trial run IDs; JSON preserves the full evaluation structure. The Evidence inspector displays declarations and flags without changing the underlying reference rules.

## V4 review propagation and audit

Planner and Critic retain backward-compatible default review fields for loading old snapshots. Gemini output requires an explicit boolean human_review field; omitted or string flags are rejected. Every successfully validated LLM flag is accumulated in WorkflowState.review_requests before semantic critique. The Safety Gate consumes those retained requests after the bounded revision loop. RunResult and SharedState preserve llm_review_requests, so a final false flag cannot erase an earlier true one.

The gateway creates a sanitized LLMCallRecord per invocation. HTTP attempt outcomes and structured-validation status are stored in the run and actual trace events. Injected gateways are labeled separately from the built-in Gemini adapter; missing key has no HTTP attempts. Raw provider errors, authorization headers and credential values are not exported. Requested model and provider-reported version are separate fields; token counts are recorded only when supplied.

ConnectionProbe uses the same adapter but no incident data. Its audit is persisted in provider_checks and displayed separately from scenario analysis. It has no effect on deterministic pilot labels or metrics. A successful probe is evidence of JSON access at that time, not fire-model validation, calibrated reliability or a guarantee that later calls succeed. Automated tests use patched transports/injected gateways; no live-provider claim follows from them.
