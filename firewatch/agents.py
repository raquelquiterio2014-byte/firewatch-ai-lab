"""Reference rules are project hypotheses, not validated fire science."""
from datetime import timedelta

from .models import Assessment, CriticReview, EvidenceResult, Plan, Proposal, Risk, SafetyResult


def evidence_agent(incident, at, stale_hours=6):
    gaps = [f"{name} is unknown" for name in ("smoke", "flames", "exposure")
            if getattr(incident, name) == "unknown"]
    conflicts = [e.id for e in incident.evidence if e.conflicts]
    stale = [e.id for e in incident.evidence if at - e.observed_at > timedelta(hours=stale_hours)]
    future = [e.id for e in incident.evidence if e.observed_at > at + timedelta(minutes=5)]
    return EvidenceResult(evidence_ids=[e.id for e in incident.evidence], gaps=gaps,
                          conflicts=conflicts, stale_ids=stale, future_ids=future)


def planner_agent(evidence):
    missing = evidence.gaps or evidence.conflicts or evidence.stale_ids or evidence.future_ids
    return Plan(tool="request_information_then_assess" if missing else "assess_evidence",
                rationale="Review evidence gaps before analysis." if missing else "Analyze the provided observations.")


def assessment_agent(incident):
    if incident.flames == "yes":
        status, reason = "STRONG_INDICATION", "Flames are present in the supplied observation; this is not independent confirmation."
    elif incident.smoke == "yes":
        status, reason = "POSSIBLE_FIRE", "Smoke is reported; its cause has not been established."
    elif incident.smoke == "no" and incident.flames == "no":
        status, reason = "NO_INDICATION", "No smoke or flames in the supplied observation; this does not establish that the area is safe."
    else:
        status, reason = "INSUFFICIENT_EVIDENCE", "The observations do not establish the presence or absence of fire indicators."
    return Assessment(status=status, rationale=reason, evidence_ids=[e.id for e in incident.evidence])


def risk_agent(incident, assessment):
    indication = assessment.status in ("STRONG_INDICATION", "POSSIBLE_FIRE")
    if indication and incident.exposure == "yes":
        level, reason = "HIGH", "Fire indicators and reported exposure of people or infrastructure."
    elif indication and incident.exposure == "unknown":
        level, reason = "UNDETERMINED", "Exposure is unknown while fire indicators are present."
    elif indication:
        level, reason = "MEDIUM", "Fire indicators with no reported exposure; contextual priority only."
    elif assessment.status == "INSUFFICIENT_EVIDENCE" or incident.exposure == "unknown":
        level, reason = "UNDETERMINED", "Available observations are insufficient to assign contextual priority."
    else:
        level, reason = "LOW", "No reported fire indicators; this is not a probability or an all-clear."
    return Risk(level=level, rationale=reason, evidence_ids=assessment.evidence_ids)


def decision_agent(assessment, risk, evidence):
    review = (assessment.status != "NO_INDICATION" or risk.level == "UNDETERMINED"
              or bool(evidence.gaps or evidence.conflicts or evidence.stale_ids or evidence.future_ids))
    questions = [f"Can a reviewer verify whether {g.replace(' is unknown', '')} is present?" for g in evidence.gaps]
    if evidence.conflicts:
        questions.append("Can the conflicting records be reconciled by their sources?")
    if evidence.stale_ids:
        questions.append("Is a more recent observation available?")
    if evidence.future_ids:
        questions.append("Can the observation timestamps be checked?")
    return Proposal(assessment_status=assessment.status, risk_level=risk.level,
                    human_review=review, rationale=f"{assessment.rationale} {risk.rationale}",
                    questions=questions[:8], evidence_ids=evidence.evidence_ids)


def critic_agent(proposal, assessment, risk, evidence):
    reasons = []
    if proposal.assessment_status != assessment.status:
        reasons.append("Proposal changes the reference assessment without verified evidence.")
    if proposal.risk_level != risk.level:
        reasons.append("Proposal changes the reference contextual priority.")
    if not set(proposal.evidence_ids) <= set(evidence.evidence_ids):
        reasons.append("Proposal cites unknown evidence IDs.")
    if not proposal.human_review and decision_agent(assessment, risk, evidence).human_review:
        reasons.append("Proposal removes a required human review.")
    return CriticReview(verdict="REVISE" if reasons else "APPROVE", reasons=reasons)


def safety_gate(assessment, risk, evidence, proposal, critic, errors, review_requests=()):
    reasons = []
    if assessment.status in ("STRONG_INDICATION", "POSSIBLE_FIRE"):
        reasons.append("Fire indicators require human review.")
    if assessment.status == "INSUFFICIENT_EVIDENCE":
        reasons.append("Insufficient evidence.")
    if risk.level == "UNDETERMINED":
        reasons.append("Contextual priority is undetermined.")
    if evidence.gaps:
        reasons.append("Unknown observation fields.")
    if evidence.conflicts:
        reasons.append("Conflicting evidence.")
    if evidence.stale_ids:
        reasons.append("Observation older than the 6-hour demonstration policy.")
    if evidence.future_ids:
        reasons.append("Observation timestamp is in the future.")
    if critic.verdict == "REVISE":
        reasons.append("Critic issues remain after the revision limit.")
    if errors:
        reasons.append("LLM fallback or validation failure.")
    reasons.extend(review_requests)
    if proposal.human_review and not reasons:
        reasons.append("Decision agent requested human review.")
    return SafetyResult(human_review_required=bool(reasons), reasons=reasons)


def reporter_agent(incident, assessment, risk, evidence, proposal, safety, mode, run_id):
    records = "\n".join(f"- [{e.id}] {e.provenance}/{e.method}; {e.source}; {e.observed_at.isoformat()}\n  {e.content}"
                        for e in incident.evidence)
    return (f"FIREWATCH AI — EDUCATIONAL PROTOTYPE\nRun: {run_id}\nMode: {mode}\n"
            f"Location: {incident.location}\n\nASSESSMENT: {assessment.status}\n{assessment.rationale}\n"
            f"\nCONTEXTUAL PRIORITY: {risk.level}\n{risk.rationale}\n"
            f"\nHUMAN REVIEW: {'REQUIRED' if safety.human_review_required else 'OPTIONAL'}\n"
            + "\n".join(f"- {r}" for r in safety.reasons)
            + f"\n\nOBSERVATIONS\nSmoke: {incident.smoke}; flames: {incident.flames}; exposure: {incident.exposure}\n"
            f"Humidity: {incident.humidity_pct}; wind: {incident.wind_kmh}; temperature: {incident.temperature_c}\n"
            f"Vegetation: {incident.vegetation}\nDescription: {incident.description}\n"
            f"\nEVIDENCE\n{records}\n\nGAPS\n" + "\n".join(evidence.gaps)
            + "\n\nDECISION PROPOSAL (may be unapproved; reference results above are retained)\n"
            + proposal.rationale + "\n\nINFORMATION TO VERIFY\n"
            + "\n".join(f"- {q}" for q in proposal.questions)
            + "\n\nLIMITATIONS\nSynthetic/reference rules are not validated fire science."
            " No independent diagnosis, propagation forecast, operational commands or calibrated confidence."
            " Human approval is a record of review, not evidence that an area is safe.\n")
