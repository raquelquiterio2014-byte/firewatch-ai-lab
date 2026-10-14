"""Deliberately simple executable checklist; not observations from a human trial."""
from .models import EvaluationDecision


DESCRIPTION = (
    "Executable simplified checklist, not a measured human baseline: reported flames -> STRONG_INDICATION/HIGH; "
    "smoke -> POSSIBLE_FIRE/MEDIUM; explicitly absent indicators -> NO_INDICATION/LOW; otherwise "
    "INSUFFICIENT_EVIDENCE/UNDETERMINED. Review fire indicators or unknown smoke/flames/exposure. "
    "It does not adjust priority for exposure or inspect age/conflict flags. Labels favor the project's richer rules; "
    "the comparison is illustrative and not evidence of superiority over professional human judgment."
)


def checklist_baseline(incident):
    if incident.flames == "yes":
        status, risk = "STRONG_INDICATION", "HIGH"
    elif incident.smoke == "yes":
        status, risk = "POSSIBLE_FIRE", "MEDIUM"
    elif incident.smoke == "no" and incident.flames == "no":
        status, risk = "NO_INDICATION", "LOW"
    else:
        status, risk = "INSUFFICIENT_EVIDENCE", "UNDETERMINED"
    review = (status != "NO_INDICATION" or "unknown" in (incident.smoke, incident.flames, incident.exposure))
    return EvaluationDecision(assessment=status, risk=risk, human_review=review)
