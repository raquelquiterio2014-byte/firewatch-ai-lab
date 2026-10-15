"""Paired synthetic comparison: offline replay or explicitly requested hybrid."""
import csv
import hashlib
import io
import json
from collections import Counter
from statistics import mean

from . import __version__
from .evaluation import LABELS, decision_fields
from .models import (ComparativeEvaluation, ComparisonMetrics, ComparisonTrial,
                     EvaluationDecision, now)
from .pipeline import Pipeline
from .gateway import configured_model
from .scenarios import get_scenario


def incident_hash(incident):
    payload = json.dumps(incident.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def integrity_issues(run):
    issues = []
    available = {e.id for e in run.incident.evidence}
    citations = [*run.assessment.evidence_ids, *run.risk.evidence_ids,
                 *run.proposal.evidence_ids, *run.evidence_result.evidence_ids]
    if run.context_result:
        citations += run.context_result.evidence_ids
    if not citations or any(c not in available for c in citations):
        issues.append("Unknown or missing citation IDs")
    if not run.trace or any(e.run_id != run.run_id for e in run.trace):
        issues.append("Missing trace or mismatched trace run IDs")
    if run.orchestrator == "langgraph" and not run.graph_steps:
        issues.append("Missing graph snapshots")
    if any(step.run_id != run.run_id for step in run.graph_steps):
        issues.append("Mismatched graph snapshot run IDs")
    if run.proposal.assessment_status != run.assessment.status or run.proposal.risk_level != run.risk.level:
        if run.critic.verdict != "REVISE" or not run.safety.human_review_required:
            issues.append("Unresolved proposal difference without rejection and human review")
    if run.llm_review_requests and not run.safety.human_review_required:
        issues.append("Retained LLM review request was removed")
    return issues


def proposal_fields(run):
    return EvaluationDecision(assessment=run.proposal.assessment_status, risk=run.proposal.risk_level,
                              human_review=run.proposal.human_review)


def comparison_metrics(rows):
    calls = [call for row in rows for call in row.candidate.llm_calls]
    provider = [call for call in calls if call.source == "gemini_api"]
    tokens = Counter()
    for call in provider:
        tokens.update(call.token_usage)
    grouped = {}
    for row in rows:
        grouped.setdefault(row.scenario, []).append(decision_fields(row.candidate))
    repeated = [decisions for decisions in grouped.values() if len(decisions) >= 2]
    return ComparisonMetrics(
        pairs=len(rows), final_decision_agreement=sum(decision_fields(r.reference) == decision_fields(r.candidate) for r in rows),
        reference_label_matches=sum(decision_fields(r.reference) == r.expected for r in rows),
        candidate_label_matches=sum(decision_fields(r.candidate) == r.expected for r in rows),
        candidate_more_reviews=sum(not r.reference.safety.human_review_required and r.candidate.safety.human_review_required for r in rows),
        candidate_removed_reviews=sum(r.reference.safety.human_review_required and not r.candidate.safety.human_review_required for r in rows),
        candidate_proposal_differences=sum(proposal_fields(r.reference) != proposal_fields(r.candidate) for r in rows),
        candidate_modes=dict(Counter(r.candidate.mode for r in rows)),
        fully_validated_provider_pairs=sum(
            r.candidate.mode == "llm" and {"Planner", "Decision", "Critic"} <= {c.component for c in r.candidate.llm_calls}
            and all(c.source == "gemini_api" and c.succeeded and c.output_validated for c in r.candidate.llm_calls)
            for r in rows),
        source_call_counts=dict(Counter(c.source for c in calls)),
        candidate_error_codes=dict(Counter(c.error_code for c in calls if c.error_code)),
        provider_http_attempts=sum(len(c.attempts) for c in provider), provider_token_usage=dict(tokens),
        intact_runs=sum(not integrity_issues(run) for r in rows for run in (r.reference, r.candidate)),
        runs_checked=2 * len(rows),
        mean_reference_ms=round(mean(r.reference.duration_ms for r in rows), 3) if rows else 0,
        mean_candidate_ms=round(mean(r.candidate.duration_ms for r in rows), 3) if rows else 0,
        candidate_stable_cases=sum(all(d == decisions[0] for d in decisions) for decisions in repeated),
        repeated_cases_checked=len(repeated),
    )


def compare(store=None, *, use_llm=False, scenario_numbers=None, repetitions=2, model=None,
            pipeline_factory=None, on_progress=None, cancel_event=None):
    if type(repetitions) is not int or not 1 <= repetitions <= 3:
        raise ValueError("Comparison repetitions must be an integer from 1 to 3")
    numbers = list(range(1, 11)) if scenario_numbers is None else list(scenario_numbers)
    if not numbers or len(set(numbers)) != len(numbers) or any(type(n) is not int or not 1 <= n <= 10 for n in numbers):
        raise ValueError("Choose unique scenario numbers from 1 to 10")
    model = model if model is not None else configured_model() if use_llm else None
    factory = pipeline_factory or (lambda: Pipeline(model=model))
    rows, status = [], "COMPLETE"
    for number in numbers:
        name, status_label, risk_label, review = LABELS[number - 1]
        incident, at = get_scenario(name), now()
        expected = EvaluationDecision(assessment=status_label, risk=risk_label, human_review=review)
        for repetition in range(1, repetitions + 1):
            if cancel_event is not None and cancel_event.is_set():
                status = "CANCELLED"
                break
            # Detached copies prevent a custom gateway/callback from changing its paired input.
            reference = factory().run(incident.model_copy(deep=True), at=at, use_llm=False)
            if store:
                store.save(reference)
            candidate = factory().run(incident.model_copy(deep=True), at=at, use_llm=use_llm)
            trial = ComparisonTrial(scenario=name, repetition=repetition, input_sha256=incident_hash(incident),
                                    expected=expected, reference=reference, candidate=candidate)
            if incident_hash(reference.incident) != trial.input_sha256:
                raise ValueError("Pipeline changed the supplied comparison input")
            if store:
                store.save(candidate)
            rows.append(trial)
            if on_progress:
                on_progress({"completed_pairs": len(rows), "requested_pairs": len(numbers) * repetitions,
                             "scenario": name, "repetition": repetition, "candidate_mode": candidate.mode})
        if status == "CANCELLED":
            break
    evaluation = ComparativeEvaluation(version=__version__,
        requested_candidate="gemini_hybrid" if use_llm else "deterministic_replay",
        requested_model=model if use_llm else None, scenarios=[LABELS[n - 1][0] for n in numbers],
        repetitions=repetitions, status=status, rows=rows, metrics=comparison_metrics(rows))
    if store:
        store.save_comparison(evaluation)
    return evaluation


def validate_comparison(data):
    evaluation = ComparativeEvaluation.model_validate(data.model_dump() if isinstance(data, ComparativeEvaluation) else data)
    for row in evaluation.rows:
        if row.input_sha256 != incident_hash(row.reference.incident):
            raise ValueError("Comparison input checksum does not match")
    if evaluation.metrics != comparison_metrics(evaluation.rows):
        raise ValueError("Comparison metrics do not match actual run snapshots")
    return evaluation


def comparison_csv(data):
    evaluation = validate_comparison(data)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["comparison_id", "scenario", "repetition", "input_sha256", "reference_run_id", "candidate_run_id",
                     "requested_candidate", "actual_candidate_mode", "reference_assessment", "candidate_assessment",
                     "reference_risk", "candidate_risk", "reference_review", "candidate_review", "final_agreement",
                     "proposal_agreement", "candidate_critic", "candidate_revisions", "reference_ms", "candidate_ms",
                     "audit_sources", "error_codes", "requested_models", "integrity_issues"])
    for row in evaluation.rows:
        ref, candidate = decision_fields(row.reference), decision_fields(row.candidate)
        writer.writerow([evaluation.comparison_id, row.scenario, row.repetition, row.input_sha256,
                         row.reference.run_id, row.candidate.run_id, evaluation.requested_candidate, row.candidate.mode,
                         ref.assessment, candidate.assessment, ref.risk, candidate.risk, ref.human_review, candidate.human_review,
                         ref == candidate, proposal_fields(row.reference) == proposal_fields(row.candidate), row.candidate.critic.verdict,
                         row.candidate.revisions, row.reference.duration_ms, row.candidate.duration_ms,
                         "|".join(sorted({c.source for c in row.candidate.llm_calls})),
                         "|".join(sorted({c.error_code for c in row.candidate.llm_calls if c.error_code})),
                         "|".join(sorted({c.requested_model for c in row.candidate.llm_calls})),
                         "|".join(integrity_issues(row.reference) + integrity_issues(row.candidate))])
    return output.getvalue()


def comparison_report(data):
    evaluation = validate_comparison(data)
    metrics = evaluation.metrics
    lines = ["FIREWATCH AI V6 — COMPARATIVE SYNTHETIC REPORT", f"Comparison: {evaluation.comparison_id}",
             f"Status: {evaluation.status}; requested candidate: {evaluation.requested_candidate}",
             f"Completed pairs: {metrics.pairs}/{len(evaluation.scenarios) * evaluation.repetitions}",
             f"Final decision agreement: {metrics.final_decision_agreement}/{metrics.pairs}",
             f"Reference/candidate label matches: {metrics.reference_label_matches}/{metrics.candidate_label_matches} (pair denominator {metrics.pairs})",
             f"Actual candidate modes: {metrics.candidate_modes}",
             f"Fully validated provider pairs: {metrics.fully_validated_provider_pairs}/{metrics.pairs}",
             f"Audit source counts: {metrics.source_call_counts}; HTTP attempts: {metrics.provider_http_attempts}",
             f"Recorded error codes: {metrics.candidate_error_codes}",
             f"Provider-reported token counts: {metrics.provider_token_usage}",
             f"Candidate more/removed reviews: {metrics.candidate_more_reviews}/{metrics.candidate_removed_reviews}",
             f"Proposal differences: {metrics.candidate_proposal_differences}",
             f"Intact runs: {metrics.intact_runs}/{metrics.runs_checked}",
             f"Repeated final decisions: {metrics.candidate_stable_cases}/{metrics.repeated_cases_checked}",
             f"Mean reference/candidate time: {metrics.mean_reference_ms}/{metrics.mean_candidate_ms} ms", ""]
    for row in evaluation.rows:
        lines.extend([f"{row.scenario} — trial {row.repetition}",
                      f"Input SHA256: {row.input_sha256}",
                      f"Reference {row.reference.run_id}: {decision_fields(row.reference).model_dump()}",
                      f"Candidate {row.candidate.run_id}: {decision_fields(row.candidate).model_dump()} ({row.candidate.mode})",
                      f"Proposal: {proposal_fields(row.candidate).model_dump()}; Critic: {row.candidate.critic.verdict}",
                      f"Integrity issues: {integrity_issues(row.reference) + integrity_issues(row.candidate)}", ""])
    return "\n".join(lines) + "\nLIMITATIONS\n" + evaluation.limitation + "\n"
