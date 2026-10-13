"""Readable summaries derived only from actual completed run outputs/events."""


def component_mode(result, component):
    events = [e for e in result.trace if e.component == component
              and e.action in ("completed", "llm_completed", "fallback", "constraint_rejected")]
    return events[-1].mode if events else "not recorded"


def agent_summary(result):
    entries = [
        ("Planner", f"Selected route: {result.plan.tool}\n{result.plan.rationale}"),
        ("Evidence", f"Records: {len(result.evidence_result.evidence_ids)}; unknown fields: {len(result.evidence_result.gaps)}; "
         f"flagged conflicts: {len(result.evidence_result.conflicts)}; old records: {len(result.evidence_result.stale_ids)}; "
         f"future records: {len(result.evidence_result.future_ids)}"),
        ("FireAssessment", f"{result.assessment.status}\n{result.assessment.rationale}"),
        ("RiskExposure", f"{result.risk.level}\n{result.risk.rationale}"),
        ("Decision", f"PROPOSAL — approval depends on Critic\n{result.proposal.rationale}\n"
         + "\n".join(f"Information to verify: {q}" for q in result.proposal.questions)),
        ("Critic", f"{result.critic.verdict}; revisions used: {result.revisions}/1\n" + "\n".join(result.critic.reasons)),
        ("SafetyGate", f"Human review: {'REQUIRED' if result.safety.human_review_required else 'OPTIONAL'}\n"
         + "\n".join(result.safety.reasons)),
        ("Reporter", "Explainable report available in the Report tab."),
    ]
    return (f"COMPLETED RUN: {result.run_id}\nExecution mode: {result.mode.upper()}\n"
            "Reference pipeline in deterministic mode; optional LLM calls are identified below.\n\n"
            + "\n\n".join(f"{name} [{component_mode(result, name)}]\n{text}" for name, text in entries)
            + "\n\nHuman Gate: review records are in Safety / Review and Shared State.\n")
