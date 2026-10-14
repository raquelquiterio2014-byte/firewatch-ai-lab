"""V1 coordinator retained for regression comparison; not the V2 default."""
import time
from uuid import uuid4

from . import agents
from .gateway import GeminiGateway
from .models import CriticReview, Event, Incident, Plan, Proposal, RunResult, now


class ReferencePipeline:
    def __init__(self, gateway=None):
        self.gateway = gateway

    def run(self, incident, use_llm=False, at=None):
        # Revalidate even a model instance: callers may have used model_copy(update=...).
        incident = Incident.model_validate(incident.model_dump() if isinstance(incident, Incident) else incident)
        at = at or now()
        started = time.perf_counter()
        run_id = str(uuid4())
        trace, errors = [], []

        def event(component, action, mode="deterministic", duration_ms=None, **details):
            trace.append(Event(run_id=run_id, component=component, action=action,
                               mode=mode, duration_ms=duration_ms, details=details))

        def reference(component, fn, *args):
            event(component, "started")
            tick = time.perf_counter()
            result = fn(*args)
            event(component, "completed", duration_ms=round((time.perf_counter()-tick)*1000, 3),
                  output=result.model_dump(mode="json"))
            return result

        event("Coordinator", "run_started", requested_mode="llm" if use_llm else "deterministic")
        evidence = reference("Evidence", agents.evidence_agent, incident, at)
        gateway = self.gateway
        llm_active = use_llm

        def reasoning(component, schema, context, default):
            nonlocal llm_active, gateway
            if not llm_active:
                event(component, "completed", mode="fallback" if errors else "deterministic",
                      output=default.model_dump(mode="json"))
                return default
            event(component, "llm_started", mode="llm")
            tick = time.perf_counter()
            try:
                if gateway is None:
                    gateway = GeminiGateway()
                response = gateway.call(component, schema, context)
                response = schema.model_validate(response.model_dump() if hasattr(response, "model_dump") else response)
                event(component, "llm_completed", mode="llm",
                      duration_ms=round((time.perf_counter()-tick)*1000, 3), output=response.model_dump(mode="json"))
                return response
            except Exception:
                # Do not log exception contents: third-party errors may contain API keys.
                errors.append(f"{component}: LLM call/validation failed; deterministic fallback")
                event(component, "fallback", mode="fallback", reason=errors[-1],
                      duration_ms=round((time.perf_counter()-tick)*1000, 3))
                llm_active = False
                return default

        plan = reasoning("Planner", Plan, {"evidence": evidence.model_dump(mode="json")}, agents.planner_agent(evidence))
        event("Coordinator", "tool_called", mode="llm" if llm_active else "deterministic", tool=plan.tool)
        if plan.tool == "request_information_then_assess":
            event("InformationRequest", "pending_human_information", gaps=evidence.gaps,
                  message="No external source is contacted; analysis continues with explicit unknowns.")
        assessment = reference("FireAssessment", agents.assessment_agent, incident)
        risk = reference("RiskExposure", agents.risk_agent, incident, assessment)
        context = {"incident": incident.model_dump(mode="json"), "evidence": evidence.model_dump(mode="json"),
                   "assessment": assessment.model_dump(mode="json"), "risk": risk.model_dump(mode="json")}
        default = agents.decision_agent(assessment, risk, evidence)
        proposal = reasoning("Decision", Proposal, context, default)

        def review():
            constraints = agents.critic_agent(proposal, assessment, risk, evidence)
            if constraints.verdict == "REVISE":
                event("Critic", "constraint_rejected", reasons=constraints.reasons)
                return constraints
            return reasoning("Critic", CriticReview, {**context, "proposal": proposal.model_dump(mode="json")}, constraints)

        critic = review()
        revisions = 0
        if critic.verdict == "REVISE":
            revisions = 1
            event("Coordinator", "revision_requested", reasons=critic.reasons)
            proposal = reasoning("Decision", Proposal, {**context, "critic": critic.model_dump(mode="json")}, default)
            critic = review()
        mode = "fallback" if errors else "llm" if use_llm else "deterministic"
        safety = reference("SafetyGate", agents.safety_gate, assessment, risk, evidence, proposal, critic, errors)
        event("Reporter", "started")
        report = agents.reporter_agent(incident, assessment, risk, evidence, proposal, safety, mode, run_id)
        event("Reporter", "completed")
        event("HumanGate", "pending" if safety.human_review_required else "optional")
        duration = round((time.perf_counter()-started)*1000, 3)
        event("Coordinator", "run_completed", mode=mode, duration_ms=duration)
        return RunResult(run_id=run_id, created_at=at, mode=mode, incident=incident, plan=plan,
                         evidence_result=evidence, assessment=assessment, risk=risk, proposal=proposal,
                         critic=critic, safety=safety, revisions=revisions, errors=errors,
                         trace=trace, report=report, duration_ms=duration)
