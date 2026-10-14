"""V2 LangGraph coordinator with real conditional routes and bounded revision."""
import time
from datetime import datetime
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from . import agents
from .gateway import GeminiGateway
from .models import (Assessment, CriticReview, Event, EvidenceQuality, EvidenceResult,
                     GraphStep, Incident, Plan, Proposal, Risk, RunResult, SafetyResult, now)
from .quality import evidence_quality


class WorkflowState(TypedDict, total=False):
    incident: Incident
    evidence: EvidenceResult
    quality: EvidenceQuality
    plan: Plan
    assessment: Assessment
    risk: Risk
    proposal: Proposal
    critic: CriticReview
    safety: SafetyResult
    revisions: int
    errors: list[str]
    llm_active: bool
    questions: list[str]
    report: str
    review_pending: bool


NODE_NAMES = ("evidence", "planner", "information_request", "fire_assessment", "risk_exposure",
              "decision", "critic", "revision", "safety_gate", "reporter", "human_gate")


def build_workflow(nodes, planner_route, critic_route):
    builder = StateGraph(WorkflowState)
    for name in NODE_NAMES:
        builder.add_node(name, nodes[name])
    builder.add_edge(START, "evidence")
    builder.add_edge("evidence", "planner")
    builder.add_conditional_edges("planner", planner_route,
                                 {"information_request": "information_request", "fire_assessment": "fire_assessment"})
    builder.add_edge("information_request", "fire_assessment")
    builder.add_edge("fire_assessment", "risk_exposure")
    builder.add_edge("risk_exposure", "decision")
    builder.add_edge("decision", "critic")
    builder.add_conditional_edges("critic", critic_route, {"revision": "revision", "safety_gate": "safety_gate"})
    builder.add_edge("revision", "decision")
    builder.add_edge("safety_gate", "reporter")
    builder.add_edge("reporter", "human_gate")
    builder.add_edge("human_gate", END)
    return builder.compile()


def workflow_mermaid():
    """Topology rendered by the same compiled graph factory used for execution."""
    nodes = {name: lambda state: {} for name in NODE_NAMES}
    graph = build_workflow(nodes, lambda state: "fire_assessment", lambda state: "safety_gate")
    return graph.get_graph().draw_mermaid()


def state_snapshot(state):
    incident = state["incident"]
    snapshot = {"observation": {"incident_id": incident.id, "location": incident.location,
                               "smoke": incident.smoke, "flames": incident.flames, "exposure": incident.exposure,
                               "humidity_pct": incident.humidity_pct, "wind_kmh": incident.wind_kmh,
                               "temperature_c": incident.temperature_c, "vegetation": incident.vegetation,
                               "evidence_ids": [e.id for e in incident.evidence]},
                "revision_count": state["revisions"], "errors": list(state["errors"]),
                "llm_active": state["llm_active"]}
    for key in ("evidence", "quality", "plan", "assessment", "risk", "proposal", "critic", "safety"):
        if key in state:
            snapshot[key] = state[key].model_dump(mode="json")
    for key in ("questions", "review_pending"):
        if key in state:
            snapshot[key] = state[key]
    return snapshot


class Pipeline:
    def __init__(self, gateway=None):
        self.gateway = gateway

    def run(self, incident, use_llm=False, at=None, on_step=None):
        incident = Incident.model_validate(incident.model_dump() if isinstance(incident, Incident) else incident)
        at = at or now()
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("Analysis time must include a timezone")
        started = time.perf_counter()
        run_id = str(uuid4())
        trace, steps = [], []
        gateway = self.gateway

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

        def reasoning(state, component, schema, context, default):
            nonlocal gateway
            if not state["llm_active"]:
                event(component, "completed", mode="fallback" if state["errors"] else "deterministic",
                      output=default.model_dump(mode="json"))
                return default, {}
            event(component, "llm_started", mode="llm")
            tick = time.perf_counter()
            try:
                if gateway is None:
                    gateway = GeminiGateway()
                response = gateway.call(component, schema, context)
                response = schema.model_validate(response.model_dump() if hasattr(response, "model_dump") else response)
                event(component, "llm_completed", mode="llm",
                      duration_ms=round((time.perf_counter()-tick)*1000, 3), output=response.model_dump(mode="json"))
                return response, {}
            except Exception:
                error = f"{component}: LLM call/validation failed; deterministic fallback"
                event(component, "fallback", mode="fallback", reason=error,
                      duration_ms=round((time.perf_counter()-tick)*1000, 3))
                return default, {"llm_active": False, "errors": [*state["errors"], error]}

        def context(state):
            return {"incident": state["incident"].model_dump(mode="json"),
                    "evidence": state["evidence"].model_dump(mode="json"),
                    "assessment": state["assessment"].model_dump(mode="json"),
                    "risk": state["risk"].model_dump(mode="json")}

        def evidence_node(state):
            checked = reference("Evidence", agents.evidence_agent, state["incident"], at)
            quality = reference("EvidenceQuality", evidence_quality, state["incident"], checked)
            return {"evidence": checked, "quality": quality}

        def planner_node(state):
            plan, update = reasoning(state, "Planner", Plan, {"evidence": state["evidence"].model_dump(mode="json")},
                                     agents.planner_agent(state["evidence"]))
            return {"plan": plan, **update}

        def planner_route(state):
            destination = "information_request" if state["plan"].tool == "request_information_then_assess" else "fire_assessment"
            event("Coordinator", "tool_called", mode="llm" if state["llm_active"] else "fallback" if state["errors"] else "deterministic",
                  tool=state["plan"].tool, next_node=destination)
            return destination

        def information_node(state):
            questions = [f"Verify the unknown field: {gap}." for gap in state["evidence"].gaps]
            if state["evidence"].conflicts:
                questions.append("Reconcile the manually flagged conflicting records.")
            if state["evidence"].stale_ids or state["evidence"].future_ids:
                questions.append("Verify record timestamps and obtain a current observation.")
            event("InformationRequest", "pending_human_information", gaps=state["evidence"].gaps,
                  questions=questions, message="No external source is contacted; unknowns remain unchanged.")
            return {"questions": questions}

        def assessment_node(state):
            return {"assessment": reference("FireAssessment", agents.assessment_agent, state["incident"])}

        def risk_node(state):
            return {"risk": reference("RiskExposure", agents.risk_agent, state["incident"], state["assessment"])}

        def decision_node(state):
            data = context(state)
            if state["revisions"]:
                data["critic"] = state["critic"].model_dump(mode="json")
            default = agents.decision_agent(state["assessment"], state["risk"], state["evidence"])
            proposal, update = reasoning(state, "Decision", Proposal, data, default)
            return {"proposal": proposal, **update}

        def critic_node(state):
            checked = agents.critic_agent(state["proposal"], state["assessment"], state["risk"], state["evidence"])
            if checked.verdict == "REVISE":
                event("Critic", "constraint_rejected", reasons=checked.reasons)
                return {"critic": checked}
            data = {**context(state), "proposal": state["proposal"].model_dump(mode="json")}
            reviewed, update = reasoning(state, "Critic", CriticReview, data, checked)
            return {"critic": reviewed, **update}

        def critic_route(state):
            destination = "revision" if state["critic"].verdict == "REVISE" and state["revisions"] < 1 else "safety_gate"
            event("Coordinator", "conditional_edge", verdict=state["critic"].verdict,
                  revisions=state["revisions"], next_node=destination)
            return destination

        def revision_node(state):
            event("Coordinator", "revision_requested", reasons=state["critic"].reasons)
            return {"revisions": state["revisions"] + 1}

        def safety_node(state):
            return {"safety": reference("SafetyGate", agents.safety_gate, state["assessment"], state["risk"],
                                        state["evidence"], state["proposal"], state["critic"], state["errors"])}

        def reporter_node(state):
            mode = "fallback" if state["errors"] else "llm" if use_llm else "deterministic"
            event("Reporter", "started")
            report = agents.reporter_agent(state["incident"], state["assessment"], state["risk"], state["evidence"],
                                            state["proposal"], state["safety"], mode, run_id)
            report += f"\nEVIDENCE QUALITY\nIndicator completeness: {state['quality'].completeness}\n{state['quality'].note}\n"
            event("Reporter", "completed")
            return {"report": report}

        def human_node(state):
            required = state["safety"].human_review_required
            event("HumanGate", "pending" if required else "optional")
            return {"review_pending": required}

        nodes = dict(zip(NODE_NAMES, (evidence_node, planner_node, information_node, assessment_node, risk_node,
                                     decision_node, critic_node, revision_node, safety_node, reporter_node, human_node)))
        graph = build_workflow(nodes, planner_route, critic_route)
        state = {"incident": incident, "errors": [], "revisions": 0, "llm_active": use_llm}
        event("Coordinator", "run_started", requested_mode="llm" if use_llm else "deterministic", orchestrator="langgraph")
        for update in graph.stream(state, config={"recursion_limit": 30}, stream_mode="updates"):
            for node, values in update.items():
                state.update(values)
                step = GraphStep(step=len(steps)+1, node=node, run_id=run_id, state=state_snapshot(state))
                steps.append(step)
                event("Coordinator", "node_completed", node=node, step=step.step)
                if on_step is not None:
                    on_step(step.model_copy(deep=True))
        mode = "fallback" if state["errors"] else "llm" if use_llm else "deterministic"
        duration = round((time.perf_counter()-started)*1000, 3)
        event("Coordinator", "run_completed", mode=mode, duration_ms=duration)
        return RunResult(schema_version="2.0", run_id=run_id, created_at=at, mode=mode,
                         incident=incident, plan=state["plan"], evidence_result=state["evidence"],
                         assessment=state["assessment"], risk=state["risk"], proposal=state["proposal"],
                         critic=state["critic"], safety=state["safety"], revisions=state["revisions"],
                         errors=state["errors"], trace=trace, report=state["report"], duration_ms=duration,
                         orchestrator="langgraph", evidence_quality=state["quality"], graph_steps=steps)
