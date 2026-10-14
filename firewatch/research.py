"""Human comparison and timestamp-filtered shadow analysis, separate from the pilot."""
import csv
import io
from datetime import datetime

from .evaluation import agreements, decision_fields
from .models import (Evidence, FireContext, Incident, ShadowAnalysis, ShadowAudit,
                     ShadowDataset, ShadowValues, Event)
from .pipeline import Pipeline


def human_comparison(result, assessments):
    actual_model = decision_fields(result)
    actual = actual_model.model_dump()
    rows = []
    # Keep only the latest entry per reviewer for this run; history remains intact.
    latest = {}
    for assessment in assessments:
        if assessment.run_id != result.run_id:
            raise ValueError("Human assessment belongs to a different run")
        key = assessment.reviewer.casefold()
        if key not in latest or assessment.recorded_at >= latest[key].recorded_at:
            latest[key] = assessment
    for assessment in latest.values():
        human = assessment.decision.model_dump()
        fields = agreements(actual_model, assessment.decision)
        rows.append({"assessment_id": assessment.assessment_id, "run_id": result.run_id,
                     "reviewer": assessment.reviewer, "recorded_at": assessment.recorded_at.isoformat(),
                     "system_output_seen": assessment.system_output_seen,
                     "rationale": assessment.rationale, "human": human, "system": actual,
                     "field_agreement": fields, "all_fields_agree": all(fields.values())})
    return {"run_id": result.run_id, "status": "RECORDED" if rows else "NOT_RECORDED",
            "reviewers_compared": len(rows), "all_fields_agree": sum(r["all_fields_agree"] for r in rows),
            "missed_reviews": sum(r["human"]["human_review"] and not actual["human_review"] for r in rows),
            "extra_reviews": sum(not r["human"]["human_review"] and actual["human_review"] for r in rows),
            "rows": rows, "limitation": "Agreement with entered judgments, not ground truth or fire accuracy. Latest entry per reviewer for this run. Output-seen entries are not a blinded baseline. Approval/rejection and checklist labels are separate."}


def human_comparison_csv(data):
    output = io.StringIO(newline="")
    columns = ["run_id", "assessment_id", "reviewer", "recorded_at", "system_output_seen",
               "human_assessment", "human_risk", "human_review", "system_assessment",
               "system_risk", "system_review", "all_fields_agree"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in data["rows"]:
        writer.writerow({**{k: row[k] for k in columns[:5]},
                         "human_assessment": row["human"]["assessment"], "human_risk": row["human"]["risk"],
                         "human_review": row["human"]["human_review"],
                         "system_assessment": row["system"]["assessment"], "system_risk": row["system"]["risk"],
                         "system_review": row["system"]["human_review"], "all_fields_agree": row["all_fields_agree"]})
    return output.getvalue()


def project_shadow(dataset, cutoff):
    if isinstance(dataset, ShadowDataset):
        payload = dataset.model_dump()
        for row, record in zip(payload["records"], dataset.records):
            row["values"] = record.values.model_dump(exclude_unset=True)
        dataset = ShadowDataset.model_validate(payload)
    else:
        dataset = ShadowDataset.model_validate(dataset)
    if not isinstance(cutoff, datetime) or cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("Cutoff must include a timezone")
    included, excluded = [], {}
    for record in dataset.records:
        reasons = []
        if record.available_at is None:
            reasons.append("availability_unknown")
        elif record.available_at > cutoff:
            reasons.append("available_after_cutoff")
        if record.evidence.observed_at > cutoff:
            reasons.append("observed_after_cutoff")
        if reasons:
            excluded[record.evidence.id] = reasons
        else:
            included.append(record)
    # An empty evidence list is deliberately blocked, not replaced by fake evidence.
    if not included:
        raise ValueError("No eligible records at this cutoff; analysis was not executed")
    candidates = {}
    for record in included:
        explicit = record.values.model_dump(exclude_unset=True)
        context = explicit.pop("context", {})
        explicit.update({"context." + key: value for key, value in context.items()})
        for key, value in explicit.items():
            candidates.setdefault(key, []).append((record.evidence.observed_at, value, record.evidence.id))
    values, context_values, links, conflicts = {}, {}, {}, []
    for key, entries in candidates.items():
        newest = max(e[0] for e in entries)
        selected = [e for e in entries if e[0] == newest]
        links[key] = [e[2] for e in selected]
        value = selected[0][1]
        if any(e[1] != value for e in selected):
            conflicts.append(key)
            field = key.split(".")[-1]
            defaults = FireContext() if key.startswith("context.") else ShadowValues()
            value = getattr(defaults, field)
        (context_values if key.startswith("context.") else values)[key.split(".")[-1]] = value
    evidence = [r.evidence.model_copy(deep=True) for r in included]
    for record in evidence:
        if any(record.id in links[key] for key in conflicts):
            record.conflicts = True
    context_ids = sorted({e for k, ids in links.items() if k.startswith("context.") for e in ids})
    incident = Incident(location=dataset.location, environment=dataset.environment,
                        evidence=evidence, context=FireContext(**context_values),
                        context_evidence_ids=context_ids, **values,
                        description="Retrospective projection of eligible normalized fields; no automatic text extraction.")
    audit = ShadowAudit(dataset_id=dataset.dataset_id, cutoff=cutoff,
                        included_ids=[r.evidence.id for r in included], excluded=excluded,
                        field_evidence_ids=links, conflicting_fields=conflicts)
    return incident, audit


def run_shadow(dataset, cutoff, store=None, pipeline=None):
    incident, audit = project_shadow(dataset, cutoff)
    # V5 shadow analysis is offline by policy. It never invokes a provider.
    result = (pipeline or Pipeline()).run(incident, at=cutoff, use_llm=False)
    result.trace.insert(0, Event(run_id=result.run_id, component="ShadowPolicy", action="cutoff_projection",
                                 mode="deterministic", details=audit.model_dump(mode="json")))
    result.report += "\nSHADOW MODE — RETROSPECTIVE / NO OPERATIONAL ACTION\n" + audit.model_dump_json(indent=2) + "\n"
    analysis = ShadowAnalysis(audit=audit, result=result)
    if store:
        store.save_shadow(analysis)
    return analysis
