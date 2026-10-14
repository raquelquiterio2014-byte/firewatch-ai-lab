# FireWatch AI — V2 Architecture

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

The gateway retains environment-only credentials, at most two attempts per call, timeout, structured validation and explicit fallback. The default mode does not call an external API. Live Gemini compatibility has not been verified; provider parsing and agent behavior are tested with offline doubles.

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
