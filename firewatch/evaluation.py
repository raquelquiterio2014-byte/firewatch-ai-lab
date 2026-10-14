"""Labels are fixed project expectations, not real-world ground truth."""
import csv
import io
from statistics import mean
from uuid import uuid4

from .baseline import DESCRIPTION, checklist_baseline
from .models import (EvaluationCase, EvaluationDecision, EvaluationMetrics, EvaluationTrial,
                     PilotEvaluation, now)
from .pipeline import Pipeline
from .scenarios import get_scenario


LABELS = [
    ("01 — No reported indicators", "NO_INDICATION", "LOW", False),
    ("02 — Smoke, unknown exposure", "POSSIBLE_FIRE", "UNDETERMINED", True),
    ("03 — Flames near people", "STRONG_INDICATION", "HIGH", True),
    ("04 — Dry vegetation, unknown indicators", "INSUFFICIENT_EVIDENCE", "UNDETERMINED", True),
    ("05 — Conflicting reports", "POSSIBLE_FIRE", "MEDIUM", True),
    ("06 — Old observation", "NO_INDICATION", "LOW", True),
    ("07 — Smoke, no reported exposure", "POSSIBLE_FIRE", "MEDIUM", True),
    ("08 — Flames, unknown exposure", "STRONG_INDICATION", "UNDETERMINED", True),
    ("09 — Dry weather, no indicators", "NO_INDICATION", "LOW", False),
    ("10 — Partial observation", "INSUFFICIENT_EVIDENCE", "UNDETERMINED", True),
]


def decision_fields(result):
    return EvaluationDecision(assessment=result.assessment.status, risk=result.risk.level,
                              human_review=result.safety.human_review_required)


def agreements(actual, expected):
    return {key: actual.model_dump()[key] == value for key, value in expected.model_dump().items()}


def aggregate_metrics(rows, completed_runs, valid_trace_runs, durations):
    def count(predicate):
        return sum(bool(predicate(row)) for row in rows)
    return EvaluationMetrics(
        cases=len(rows), system_case_matches=count(lambda r: r.passed),
        baseline_case_matches=count(lambda r: r.baseline_passed),
        system_field_matches={key: count(lambda r: r.field_agreement[key]) for key in ("assessment", "risk", "human_review")},
        baseline_field_matches={key: count(lambda r: r.baseline_field_agreement[key]) for key in ("assessment", "risk", "human_review")},
        expected_reviews=count(lambda r: r.expected.human_review),
        system_required_reviews=count(lambda r: r.actual.human_review),
        system_missed_reviews=count(lambda r: r.expected.human_review and not r.actual.human_review),
        system_extra_reviews=count(lambda r: not r.expected.human_review and r.actual.human_review),
        baseline_missed_reviews=count(lambda r: r.expected.human_review and not r.baseline.human_review),
        baseline_extra_reviews=count(lambda r: not r.expected.human_review and r.baseline.human_review),
        reproducible_cases=count(lambda r: r.reproducible),
        valid_citation_ids=sum(row.valid_citation_ids for row in rows),
        citation_ids_checked=sum(row.citation_ids_checked for row in rows),
        valid_trace_run_ids=valid_trace_runs, completed_runs=completed_runs,
        mean_duration_ms=round(mean(durations), 3) if durations else 0,
    )


def evaluate(store=None, repetitions=2, pipeline_factory=Pipeline):
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or not 2 <= repetitions <= 5:
        raise ValueError("Repetitions must be an integer from 2 to 5")
    rows = []
    durations, valid_trace_runs = [], 0
    for name, status, risk, review in LABELS:
        incident = get_scenario(name)
        at = now()  # Freeze analysis time for repeated runs of exactly the same input.
        expected = EvaluationDecision(assessment=status, risk=risk, human_review=review)
        trials = []
        results = []
        for _ in range(repetitions):
            result = pipeline_factory().run(incident, at=at)
            if store:
                store.save(result)
            results.append(result)
            trials.append(EvaluationTrial(run_id=result.run_id, actual=decision_fields(result), duration_ms=result.duration_ms))
            durations.append(result.duration_ms)
            valid_trace_runs += bool(result.trace) and all(event.run_id == result.run_id for event in result.trace)
        first = results[0]
        actual, baseline = trials[0].actual, checklist_baseline(incident)
        fields, baseline_fields = agreements(actual, expected), agreements(baseline, expected)
        citations = [*first.assessment.evidence_ids, *first.risk.evidence_ids, *first.proposal.evidence_ids]
        available = {record.id for record in first.incident.evidence}
        rows.append(EvaluationCase(
            scenario=name, expected=expected, actual=actual, field_agreement=fields,
            passed=all(fields.values()), run_id=first.run_id, duration_ms=first.duration_ms,
            baseline=baseline, baseline_field_agreement=baseline_fields, baseline_passed=all(baseline_fields.values()),
            trials=trials, reproducible=all(trial.actual == actual for trial in trials),
            valid_citation_ids=sum(citation in available for citation in citations), citation_ids_checked=len(citations),
        ))
    metrics = aggregate_metrics(rows, len(durations), valid_trace_runs, durations)
    evaluation = PilotEvaluation(
        evaluation_id=str(uuid4()), evaluated_at=now(), repetitions=repetitions,
        baseline_description=DESCRIPTION, total=len(rows), passed=metrics.system_case_matches,
        metrics=metrics, rows=rows,
        limitation="Synthetic, deterministic protocol with authored rule labels. Baseline is an executable simplified checklist, not observed human judgment. Citation-ID validity does not verify evidence truth; repeated-decision agreement does not measure field reliability. Review time, real fires and live LLM evaluation are not measured.",
    )
    if store:
        store.save_evaluation(evaluation)
    return evaluation.model_dump(mode="json")


def evaluation_csv(data):
    evaluation = PilotEvaluation.model_validate(data)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["evaluation_id", "scenario", "expected_assessment", "actual_assessment", "expected_risk", "actual_risk",
                     "expected_review", "actual_review", "system_passed", "baseline_assessment", "baseline_risk",
                     "baseline_review", "baseline_passed", "reproducible", "valid_citation_ids", "citation_ids_checked", "run_id", "trial_run_ids"])
    for row in evaluation.rows:
        writer.writerow([evaluation.evaluation_id, row.scenario, row.expected.assessment, row.actual.assessment,
                         row.expected.risk, row.actual.risk, row.expected.human_review, row.actual.human_review,
                         row.passed, row.baseline.assessment, row.baseline.risk, row.baseline.human_review,
                         row.baseline_passed, row.reproducible, row.valid_citation_ids, row.citation_ids_checked,
                         row.run_id, "|".join(trial.run_id for trial in row.trials)])
    return output.getvalue()
