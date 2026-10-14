"""Descriptive context agent; no invented scientific thresholds."""
from .models import ContextResult


def context_agent(incident):
    values = incident.context.model_dump()
    unknown = [key for key, value in values.items() if value in (None, "unknown")]
    concerns = []
    if len(unknown) < len(values) and not incident.context_evidence_ids:
        concerns.append("Entered context has no linked evidence; verify its source.")
    if incident.exposure == "no" and (incident.context.people_present == "yes"
                                      or incident.context.critical_infrastructure == "yes"):
        concerns.append("Exposure is declared absent but people or critical infrastructure are reported present; reconcile the context.")
    if incident.context.access_status in ("blocked", "limited") and (
            incident.smoke == "yes" or incident.flames == "yes"):
        concerns.append("Reported fire indicators and restricted access require human verification; no access action is issued.")
    return ContextResult(values=incident.context.model_copy(deep=True),
                         evidence_ids=list(incident.context_evidence_ids),
                         unknown_fields=unknown, concerns=concerns,
                         human_review_required=bool(concerns))
