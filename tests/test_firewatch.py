import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from firewatch import agents
from firewatch.evaluation import evaluate
from firewatch.gateway import GeminiGateway, GatewayError
from firewatch.models import CriticReview, Evidence, HumanReview, Incident, Plan, Proposal, now
from firewatch.pipeline import Pipeline
from firewatch.scenarios import get_scenario, sample
from firewatch.storage import Store


class ScriptedGateway:
    """Offline test double; never described as a real model invocation."""
    def __init__(self, *, reject=False, remove_gate=False, bad_id=False, fail=False, bad_schema=False):
        self.calls = []
        self.reject, self.remove_gate, self.bad_id = reject, remove_gate, bad_id
        self.fail, self.bad_schema = fail, bad_schema

    def call(self, component, schema, context):
        self.calls.append(component)
        if self.fail:
            raise TimeoutError("secret API key must not appear in result")
        if self.bad_schema:
            return {"bogus": True}
        if component == "Planner":
            return Plan(tool="request_information_then_assess", rationale="Request human information first.")
        if component == "Critic":
            return CriticReview(verdict="REVISE" if self.reject else "APPROVE", reasons=["Test rejection"] if self.reject else [])
        assessment, risk, evidence = context["assessment"], context["risk"], context["evidence"]
        return Proposal(assessment_status=assessment["status"], risk_level=risk["level"],
                        human_review=not self.remove_gate, rationale="Grounded test proposal.", questions=[],
                        evidence_ids=["invented"] if self.bad_id else evidence["evidence_ids"])


class ModelTests(unittest.TestCase):
    def test_unknown_is_preserved(self):
        incident = sample("Unknown")
        self.assertEqual(incident.flames, "unknown")
        self.assertIsNone(incident.humidity_pct)
        result = Pipeline().run(incident)
        self.assertEqual(result.assessment.status, "INSUFFICIENT_EVIDENCE")
        self.assertTrue(result.safety.human_review_required)

    def test_invalid_numeric_values_rejected(self):
        for key, value in [("humidity_pct", -1), ("humidity_pct", 101), ("wind_kmh", -1),
                           ("temperature_c", float("nan")), ("wind_kmh", float("inf"))]:
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                sample("Invalid", **{key: value})

    def test_timezone_required(self):
        with self.assertRaises(ValidationError):
            Evidence(source="Test", content="Data", observed_at="2026-10-12T10:00:00")

    def test_duplicate_ids_rejected(self):
        record = Evidence(source="Test", content="Data")
        with self.assertRaises(ValidationError):
            Incident(location="Test", evidence=[record, record])

    def test_mutated_instance_revalidated(self):
        incident = sample("Bad").model_copy(update={"humidity_pct": 200})
        with self.assertRaises(ValidationError):
            Pipeline().run(incident)


class PipelineTests(unittest.TestCase):
    def test_catalogue_labels(self):
        result = evaluate()
        self.assertEqual(result["passed"], 10)
        self.assertEqual(result["mode"], "deterministic")

    def test_flames_exposure_review(self):
        result = Pipeline().run(sample("Flames", flames="yes", exposure="yes"))
        self.assertEqual(result.assessment.status, "STRONG_INDICATION")
        self.assertEqual(result.risk.level, "HIGH")
        self.assertTrue(result.safety.human_review_required)

    def test_dry_weather_does_not_confirm_fire(self):
        result = Pipeline().run(sample("Dry", smoke="no", flames="no", exposure="no", humidity_pct=5, vegetation="dry"))
        self.assertEqual(result.assessment.status, "NO_INDICATION")
        self.assertIn("does not establish", result.assessment.rationale)

    def test_staleness_and_conflicts_force_review(self):
        for values in ({"stale": True}, {"conflict": True}):
            with self.subTest(values=values):
                result = Pipeline().run(sample("Record", smoke="no", flames="no", exposure="no", **values))
                self.assertTrue(result.safety.human_review_required)

    def test_future_record_forces_review(self):
        incident = sample("Future", smoke="no", flames="no", exposure="no")
        incident.evidence[0].observed_at = now() + timedelta(hours=1)
        result = Pipeline().run(incident)
        self.assertTrue(result.evidence_result.future_ids)
        self.assertTrue(result.safety.human_review_required)

    def test_llm_selected_tool_executes(self):
        gateway = ScriptedGateway()
        result = Pipeline(gateway).run(sample("LLM", smoke="no", flames="no", exposure="no"), use_llm=True)
        self.assertEqual(result.mode, "llm")
        self.assertEqual(gateway.calls, ["Planner", "Decision", "Critic"])
        self.assertTrue(any(e.component == "InformationRequest" for e in result.trace))

    def test_timeout_falls_back_and_does_not_log_secret(self):
        result = Pipeline(ScriptedGateway(fail=True)).run(sample("Timeout", smoke="no", flames="no", exposure="no"), use_llm=True)
        self.assertEqual(result.mode, "fallback")
        self.assertTrue(result.safety.human_review_required)
        self.assertNotIn("secret API key", result.model_dump_json())

    def test_invalid_schema_falls_back(self):
        result = Pipeline(ScriptedGateway(bad_schema=True)).run(sample("Schema"), use_llm=True)
        self.assertEqual(result.mode, "fallback")

    def test_critic_loop_is_bounded(self):
        gateway = ScriptedGateway(reject=True)
        result = Pipeline(gateway).run(sample("Critic"), use_llm=True)
        self.assertEqual(result.revisions, 1)
        self.assertEqual(gateway.calls.count("Critic"), 2)
        self.assertEqual(result.critic.verdict, "REVISE")
        self.assertTrue(result.safety.human_review_required)

    def test_llm_cannot_remove_required_gate(self):
        result = Pipeline(ScriptedGateway(remove_gate=True)).run(sample("Flames", flames="yes", exposure="yes"), use_llm=True)
        self.assertTrue(result.safety.human_review_required)
        self.assertEqual(result.critic.verdict, "REVISE")

    def test_invented_evidence_rejected(self):
        result = Pipeline(ScriptedGateway(bad_id=True)).run(sample("Citation"), use_llm=True)
        self.assertEqual(result.critic.verdict, "REVISE")
        self.assertTrue(result.safety.human_review_required)

    def test_trace_uses_real_run_ids_and_events(self):
        result = Pipeline().run(sample("Trace"))
        self.assertTrue(all(e.run_id == result.run_id for e in result.trace))
        self.assertEqual(result.trace[0].action, "run_started")
        self.assertEqual(result.trace[-1].action, "run_completed")


class GatewayTests(unittest.TestCase):
    def test_missing_key_does_not_call_network(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}), patch("firewatch.gateway.urlopen") as network:
            with self.assertRaises(GatewayError):
                GeminiGateway().call("Planner", Plan, {})
            network.assert_not_called()

    def test_valid_structured_response(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self, *_):
                return json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps({"tool": "assess_evidence", "rationale": "Test"})}]}}]}).encode()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch("firewatch.gateway.urlopen", return_value=Response()) as network:
            result = GeminiGateway().call("Planner", Plan, {})
            request = network.call_args.args[0]
            self.assertNotIn("test-key", request.full_url)
            payload = json.loads(request.data)
            self.assertIn("responseFormat", payload["generationConfig"])
            self.assertEqual(result.tool, "assess_evidence")


class StorageTests(unittest.TestCase):
    def test_run_and_review_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            result = Pipeline().run(sample("Storage"))
            store.save(result)
            restored = store.load(result.run_id)
            self.assertEqual(restored.model_dump(), result.model_dump())
            store.review(HumanReview(run_id=result.run_id, decision="REJECTED", reviewer="Raquel", comment="More evidence needed"))
            self.assertEqual(store.reviews(result.run_id)[0].decision, "REJECTED")
            lines = Path(directory, "trace.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), len(result.trace))
            self.assertEqual(store.recent()[0][0], result.run_id)

    def test_review_requires_existing_run(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(sqlite3.IntegrityError):
                Store(directory).review(HumanReview(run_id="missing", decision="APPROVED", reviewer="Test", comment="Test"))

    def test_worker_connection_is_supported(self):
        import threading
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            failures = []
            result = Pipeline().run(sample("Worker"))
            def work():
                try: store.save(result)
                except Exception as exc: failures.append(exc)
            worker = threading.Thread(target=work)
            worker.start()
            worker.join()
            self.assertFalse(failures)
            self.assertEqual(store.load(result.run_id).run_id, result.run_id)


if __name__ == "__main__":
    unittest.main()
