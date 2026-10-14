from collections import Counter

from .models import EvidenceQuality


def evidence_quality(incident, evidence):
    fields = [name for name in ("smoke", "flames", "exposure") if getattr(incident, name) == "unknown"]
    known = 3 - len(fields)
    return EvidenceQuality(
        completeness="COMPLETE" if known == 3 else "INSUFFICIENT" if known == 0 else "PARTIAL",
        known_indicator_fields=known, unknown_fields=fields, stale_ids=evidence.stale_ids,
        future_ids=evidence.future_ids, flagged_conflicts=evidence.conflicts,
        provenance_counts=dict(Counter(record.provenance for record in incident.evidence)),
    )
