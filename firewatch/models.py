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
