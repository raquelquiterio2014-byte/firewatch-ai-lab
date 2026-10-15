from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def now():
    return datetime.now(timezone.utc)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


Observation = Literal["yes", "no", "unknown"]
FireStatus = Literal["NO_INDICATION", "POSSIBLE_FIRE", "STRONG_INDICATION", "INSUFFICIENT_EVIDENCE"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "UNDETERMINED"]


class FireContext(Model):
    """Declared context, never inferred from prose or treated as a fire diagnosis."""
    fuel_type: Literal["grass", "shrub", "forest", "mixed", "unknown"] = "unknown"
    vegetation_density: Literal["sparse", "moderate", "dense", "unknown"] = "unknown"
    slope_deg: float | None = Field(default=None, ge=0, le=90)
    wind_direction: Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW", "unknown"] = "unknown"
    gust_kmh: float | None = Field(default=None, ge=0, le=500)
    distance_to_people_m: float | None = Field(default=None, ge=0, le=1000000)
    distance_to_infrastructure_m: float | None = Field(default=None, ge=0, le=1000000)
    people_present: Observation = "unknown"
    critical_infrastructure: Observation = "unknown"
    access_status: Literal["open", "limited", "blocked", "unknown"] = "unknown"


class ContextResult(Model):
    values: FireContext
    evidence_ids: list[str]
    unknown_fields: list[str]
    concerns: list[str]
    human_review_required: bool
    note: str = "Declared context only. No spread forecast, calibrated thresholds or independently verified exposure. Core fire and priority rules are unchanged."


class Evidence(Model):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str = Field(min_length=1, max_length=200)
    method: Literal["manual", "sensor", "document"] = "manual"
    provenance: Literal["synthetic", "reported", "measured"] = "synthetic"
    observed_at: datetime = Field(default_factory=now)
    content: str = Field(min_length=1, max_length=5000)
    reference: str | None = None
    conflicts: bool = False

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Observation time must include a timezone")
        return value


class Incident(Model):
    id: str = Field(default_factory=lambda: str(uuid4()))
    location: str = Field(min_length=1, max_length=200)
    environment: Literal["vegetation", "urban_interface"] = "urban_interface"
    smoke: Observation = "unknown"
    flames: Observation = "unknown"
    exposure: Observation = "unknown"
    humidity_pct: float | None = Field(default=None, ge=0, le=100)
    wind_kmh: float | None = Field(default=None, ge=0, le=500)
    temperature_c: float | None = Field(default=None, ge=-100, le=100)
    vegetation: Literal["dry", "not_dry", "unknown"] = "unknown"
    description: str = Field(default="", max_length=5000)
    evidence: list[Evidence] = Field(min_length=1, max_length=50)
    context: FireContext = Field(default_factory=FireContext)
    context_evidence_ids: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("location")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Location cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def unique_evidence(self):
        if len({e.id for e in self.evidence}) != len(self.evidence):
            raise ValueError("Evidence IDs must be unique")
        if not set(self.context_evidence_ids) <= {e.id for e in self.evidence}:
            raise ValueError("Context must cite existing evidence IDs")
        return self


class EvidenceResult(Model):
    evidence_ids: list[str]
    gaps: list[str]
    conflicts: list[str]
    stale_ids: list[str]
    future_ids: list[str]


class Assessment(Model):
    status: FireStatus
    rationale: str
    evidence_ids: list[str]


class Risk(Model):
    level: RiskLevel
    rationale: str
    evidence_ids: list[str]


class Plan(Model):
    tool: Literal["assess_evidence", "request_information_then_assess"]
    rationale: str = Field(min_length=1, max_length=2000)
    human_review: bool = False


class Proposal(Model):
    assessment_status: FireStatus
    risk_level: RiskLevel
    human_review: bool
    rationale: str = Field(min_length=1, max_length=3000)
    questions: list[str] = Field(max_length=8)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)


class CriticReview(Model):
    verdict: Literal["APPROVE", "REVISE"]
    reasons: list[str] = Field(max_length=12)
    human_review: bool = False


class SafetyResult(Model):
    human_review_required: bool
    reasons: list[str]


class Event(Model):
    run_id: str
    at: datetime = Field(default_factory=now)
    component: str
    action: str
    mode: str
    duration_ms: float | None = None
    details: dict = Field(default_factory=dict)


class EvidenceQuality(Model):
    completeness: Literal["COMPLETE", "PARTIAL", "INSUFFICIENT"]
    known_indicator_fields: int = Field(ge=0, le=3)
    unknown_fields: list[str]
    stale_ids: list[str]
    future_ids: list[str]
    flagged_conflicts: list[str]
    provenance_counts: dict[str, int]
    note: str = "Descriptive checks only; source declarations are not independently verified. No probability or confidence score."


class GraphStep(Model):
    step: int = Field(ge=1)
    node: str
    run_id: str
    state: dict


class LLMAttempt(Model):
    attempt: int = Field(ge=1, le=2)
    status: Literal["SUCCESS", "HTTP_ERROR", "NETWORK_ERROR", "INVALID_OUTPUT", "BLOCKED"]
    duration_ms: float = Field(ge=0)
    http_status: int | None = None


class LLMCallRecord(Model):
    call_id: str = Field(default_factory=lambda: str(uuid4()))
    component: str
    requested_model: str
    source: Literal["gemini_api", "injected_gateway", "configuration"]
    started_at: datetime = Field(default_factory=now)
    succeeded: bool = False
    output_validated: bool = False
    error_code: str | None = None
    attempts: list[LLMAttempt] = Field(default_factory=list, max_length=2)
    reported_model_version: str | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)


class ConnectionProbe(Model):
    status: Literal["ok"]


class RunResult(Model):
    schema_version: str = "1.0"
    rules_version: str = "educational-1.0"
    run_id: str
    created_at: datetime
    mode: Literal["deterministic", "llm", "fallback"]
    incident: Incident
    plan: Plan
    evidence_result: EvidenceResult
    assessment: Assessment
    risk: Risk
    proposal: Proposal
    critic: CriticReview
    safety: SafetyResult
    revisions: int
    errors: list[str]
    trace: list[Event]
    report: str
    duration_ms: float
    orchestrator: str = "python-v1"
    evidence_quality: EvidenceQuality | None = None
    graph_steps: list[GraphStep] = Field(default_factory=list)
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    llm_review_requests: list[str] = Field(default_factory=list)
    context_result: ContextResult | None = None


class HumanReview(Model):
    run_id: str
    decision: Literal["APPROVED", "REJECTED"]
    reviewer: str = Field(min_length=1, max_length=200)
    comment: str = Field(min_length=1, max_length=3000)
    at: datetime = Field(default_factory=now)

    @field_validator("reviewer", "comment")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Reviewer and comment must not be blank")
        return value.strip()


class SharedState(Model):
    """Read-only-by-convention snapshot of completed outputs, not a live agent bus."""
    run_id: str
    execution_mode: Literal["deterministic", "llm", "fallback"]
    incident: Incident
    planner: Plan
    evidence: EvidenceResult
    fire_assessment: Assessment
    risk_exposure: Risk
    decision: Proposal
    critic: CriticReview
    safety_gate: SafetyResult
    revision_count: int = Field(ge=0, le=1)
    errors: list[str]
    human_reviews: list[HumanReview] = Field(default_factory=list)
    orchestrator: str = "python-v1"
    evidence_quality: EvidenceQuality | None = None
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    llm_review_requests: list[str] = Field(default_factory=list)
    context_result: ContextResult | None = None

    @classmethod
    def from_run(cls, result, reviews=()):
        # Validate serialized copies so editing this view cannot alter persisted results.
        return cls.model_validate({
            "run_id": result.run_id, "execution_mode": result.mode,
            "incident": result.incident.model_dump(mode="json"),
            "planner": result.plan.model_dump(mode="json"),
            "evidence": result.evidence_result.model_dump(mode="json"),
            "fire_assessment": result.assessment.model_dump(mode="json"),
            "risk_exposure": result.risk.model_dump(mode="json"),
            "decision": result.proposal.model_dump(mode="json"),
            "critic": result.critic.model_dump(mode="json"),
            "safety_gate": result.safety.model_dump(mode="json"),
            "revision_count": result.revisions, "errors": list(result.errors),
            "human_reviews": [review.model_dump(mode="json") for review in reviews],
            "orchestrator": result.orchestrator,
            "evidence_quality": result.evidence_quality.model_dump(mode="json") if result.evidence_quality else None,
            "llm_calls": [call.model_dump(mode="json") for call in result.llm_calls],
            "llm_review_requests": list(result.llm_review_requests),
            "context_result": result.context_result.model_dump(mode="json") if result.context_result else None,
        })


class EvaluationDecision(Model):
    assessment: FireStatus
    risk: RiskLevel
    human_review: bool


class HumanAssessment(Model):
    """An entered human judgment; distinct from approval and synthetic labels."""
    assessment_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=3000)
    decision: EvaluationDecision
    system_output_seen: bool = Field(strict=True)
    recorded_at: datetime = Field(default_factory=now)

    _aware = field_validator("recorded_at")(Evidence.timezone_required.__func__)
    _nonblank = field_validator("reviewer", "rationale")(HumanReview.nonblank.__func__)


class ShadowValues(Model):
    # None / unknown is an explicit observation when entered, not an absent update.
    smoke: Observation = "unknown"
    flames: Observation = "unknown"
    exposure: Observation = "unknown"
    humidity_pct: float | None = Field(default=None, ge=0, le=100)
    wind_kmh: float | None = Field(default=None, ge=0, le=500)
    temperature_c: float | None = Field(default=None, ge=-100, le=100)
    vegetation: Literal["dry", "not_dry", "unknown"] = "unknown"
    context: FireContext = Field(default_factory=FireContext)


class ShadowRecord(Model):
    evidence: Evidence
    available_at: datetime | None = None
    values: ShadowValues
    _aware = field_validator("available_at")(lambda v: Evidence.timezone_required(v) if v is not None else None)


class ShadowDataset(Model):
    dataset_id: str = Field(default_factory=lambda: str(uuid4()))
    location: str = Field(min_length=1, max_length=200)
    environment: Literal["vegetation", "urban_interface"] = "urban_interface"
    records: list[ShadowRecord] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_records(self):
        if len({r.evidence.id for r in self.records}) != len(self.records):
            raise ValueError("Shadow evidence IDs must be unique")
        return self


class ShadowAudit(Model):
    dataset_id: str
    cutoff: datetime
    included_ids: list[str]
    excluded: dict[str, list[str]]
    field_evidence_ids: dict[str, list[str]]
    conflicting_fields: list[str]
    policy: str = "Require observed_at and declared available_at <= cutoff. Latest observation per explicitly supplied field; ties with different values become unknown. No post-cutoff text reaches analysis. Availability declarations are not independently verified."
    _aware = field_validator("cutoff")(Evidence.timezone_required.__func__)


class ShadowAnalysis(Model):
    shadow_id: str = Field(default_factory=lambda: str(uuid4()))
    executed_at: datetime = Field(default_factory=now)
    audit: ShadowAudit
    result: RunResult

    @model_validator(mode="after")
    def audit_matches_run(self):
        ids = {record.id for record in self.result.incident.evidence}
        if self.result.mode != "deterministic" or self.result.llm_calls:
            raise ValueError("Shadow analysis must be offline and deterministic")
        if self.result.created_at != self.audit.cutoff:
            raise ValueError("Shadow cutoff must match the run's analysis time")
        if ids != set(self.audit.included_ids) or ids.intersection(self.audit.excluded):
            raise ValueError("Shadow evidence must match the included audit IDs")
        return self


class EvaluationTrial(Model):
    run_id: str
    actual: EvaluationDecision
    duration_ms: float = Field(ge=0)


class EvaluationCase(Model):
    scenario: str
    expected: EvaluationDecision
    actual: EvaluationDecision
    field_agreement: dict[str, bool]
    passed: bool
    run_id: str
    duration_ms: float = Field(ge=0)
    baseline: EvaluationDecision
    baseline_field_agreement: dict[str, bool]
    baseline_passed: bool
    trials: list[EvaluationTrial] = Field(min_length=2)
    reproducible: bool
    valid_citation_ids: int = Field(ge=0)
    citation_ids_checked: int = Field(ge=0)


class EvaluationMetrics(Model):
    cases: int = Field(ge=0)
    system_case_matches: int = Field(ge=0)
    baseline_case_matches: int = Field(ge=0)
    system_field_matches: dict[str, int]
    baseline_field_matches: dict[str, int]
    expected_reviews: int = Field(ge=0)
    system_required_reviews: int = Field(ge=0)
    system_missed_reviews: int = Field(ge=0)
    system_extra_reviews: int = Field(ge=0)
    baseline_missed_reviews: int = Field(ge=0)
    baseline_extra_reviews: int = Field(ge=0)
    reproducible_cases: int = Field(ge=0)
    valid_citation_ids: int = Field(ge=0)
    citation_ids_checked: int = Field(ge=0)
    valid_trace_run_ids: int = Field(ge=0)
    completed_runs: int = Field(ge=0)
    mean_duration_ms: float = Field(ge=0)


class PilotEvaluation(Model):
    evaluation_id: str
    evaluated_at: datetime
    version: str = "3.0.0"
    rules_version: str = "educational-1.0"
    mode: Literal["deterministic"] = "deterministic"
    synthetic: Literal[True] = True
    repetitions: int = Field(ge=2, le=5)
    baseline_description: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    metrics: EvaluationMetrics
    rows: list[EvaluationCase]
    limitation: str


class ComparisonTrial(Model):
    scenario: str
    repetition: int = Field(ge=1, le=3)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected: EvaluationDecision
    reference: RunResult
    candidate: RunResult

    @model_validator(mode="after")
    def same_input_and_time(self):
        if self.reference.run_id == self.candidate.run_id:
            raise ValueError("Comparison requires distinct run IDs")
        if self.reference.mode != "deterministic" or self.reference.llm_calls:
            raise ValueError("Comparison reference must be deterministic")
        if self.reference.incident != self.candidate.incident or self.reference.created_at != self.candidate.created_at:
            raise ValueError("Paired comparison inputs and analysis times must match")
        return self


class ComparisonMetrics(Model):
    pairs: int = Field(ge=0)
    final_decision_agreement: int = Field(ge=0)
    reference_label_matches: int = Field(ge=0)
    candidate_label_matches: int = Field(ge=0)
    candidate_more_reviews: int = Field(ge=0)
    candidate_removed_reviews: int = Field(ge=0)
    candidate_proposal_differences: int = Field(ge=0)
    candidate_modes: dict[str, int]
    fully_validated_provider_pairs: int = Field(ge=0)
    source_call_counts: dict[str, int]
    candidate_error_codes: dict[str, int]
    provider_http_attempts: int = Field(ge=0)
    provider_token_usage: dict[str, int]
    intact_runs: int = Field(ge=0)
    runs_checked: int = Field(ge=0)
    mean_reference_ms: float = Field(ge=0)
    mean_candidate_ms: float = Field(ge=0)
    candidate_stable_cases: int = Field(ge=0)
    repeated_cases_checked: int = Field(ge=0)


class ComparativeEvaluation(Model):
    comparison_id: str = Field(default_factory=lambda: str(uuid4()))
    evaluated_at: datetime = Field(default_factory=now)
    version: str = "6.0.0"
    synthetic: Literal[True] = True
    requested_candidate: Literal["deterministic_replay", "gemini_hybrid"]
    requested_model: str | None = None
    scenarios: list[str] = Field(min_length=1, max_length=10)
    repetitions: int = Field(ge=1, le=3)
    status: Literal["COMPLETE", "CANCELLED"]
    rows: list[ComparisonTrial] = Field(max_length=30)
    metrics: ComparisonMetrics
    limitation: str = "Authored synthetic labels, not fire accuracy. Assessment and priority remain rule-based in both modes; hybrid reasoning concerns routing, proposals and critique. Reported provider access requires successful gemini_api audit records; injected fixtures and fallback are separate. Token counts are provider reports, not billing estimates. Human judgments are separate, never inferred from labels."

    @model_validator(mode="after")
    def complete_unique_pairs(self):
        ids = [run.run_id for row in self.rows for run in (row.reference, row.candidate)]
        if len(ids) != len(set(ids)):
            raise ValueError("Comparison run IDs must be globally unique")
        keys = [(r.scenario, r.repetition) for r in self.rows]
        if len(keys) != len(set(keys)) or len(self.scenarios) != len(set(self.scenarios)):
            raise ValueError("Comparison cases and trial keys must be unique")
        if any(r.scenario not in self.scenarios or r.repetition > self.repetitions for r in self.rows):
            raise ValueError("Comparison row is outside the requested protocol")
        if self.status == "COMPLETE" and len(self.rows) != len(self.scenarios) * self.repetitions:
            raise ValueError("Complete comparison must contain all requested pairs")
        if self.metrics.pairs != len(self.rows) or self.metrics.runs_checked != 2 * len(self.rows):
            raise ValueError("Comparison metric denominators must match paired runs")
        inputs = {}
        for row in self.rows:
            signature = (row.input_sha256, row.reference.created_at)
            if row.scenario in inputs and inputs[row.scenario] != signature:
                raise ValueError("Repeated trials must use the same input and analysis time")
            inputs[row.scenario] = signature
        if self.requested_candidate == "deterministic_replay" and any(
                r.candidate.mode != "deterministic" or r.candidate.llm_calls for r in self.rows):
            raise ValueError("Offline replay cannot claim hybrid or provider execution")
        return self
