import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from firewatch.gateway import GeminiGateway, GatewayError, configuration_status
from firewatch.integration import check_gemini
from firewatch.models import ConnectionProbe, CriticReview, Plan, Proposal
from firewatch.pipeline import Pipeline
from firewatch.scenarios import sample
from firewatch.storage import Store


class Response:
    def __init__(self, output=None, finish="STOP", raw=None):
        self.raw = raw or json.dumps({
            "modelVersion": "gemini-2.5-flash", "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5,
                                                                      "totalTokenCount": 15, "ignored": "private"},
            "candidates": [{"finishReason": finish, "content": {"parts": [{"text": json.dumps(output)}]}}],
        }).encode()
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, *_): return self.raw


class GatewayV4Tests(unittest.TestCase):
    def test_string_review_flag_is_invalid_output(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), \
             patch("firewatch.gateway.urlopen", return_value=Response({"tool": "assess_evidence", "rationale": "Wrong type", "human_review": "false"})):
            gateway = GeminiGateway()
            with self.assertRaises(GatewayError): gateway.call("Planner", Plan, {})
            self.assertEqual(gateway.last_call.error_code, "INVALID_OUTPUT")

    def test_missing_explicit_review_flag_is_invalid_output(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), \
             patch("firewatch.gateway.urlopen", return_value=Response({"tool": "assess_evidence", "rationale": "No review field"})):
            gateway = GeminiGateway()
            with self.assertRaises(GatewayError): gateway.call("Planner", Plan, {})
            self.assertEqual(gateway.last_call.error_code, "INVALID_OUTPUT")

    def test_missing_key_records_zero_attempts_without_network(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}), patch("firewatch.gateway.urlopen") as network:
            gateway = GeminiGateway()
            with self.assertRaises(GatewayError): gateway.call("ConnectionProbe", ConnectionProbe, {})
            self.assertEqual(gateway.last_call.error_code, "MISSING_KEY")
            self.assertEqual(gateway.last_call.attempts, [])
            network.assert_not_called()

    def test_successful_probe_metadata_and_key_redaction(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), patch("firewatch.gateway.urlopen", return_value=Response({"status": "ok"})):
            record = check_gemini()
            self.assertTrue(record.succeeded)
            self.assertTrue(record.output_validated)
            self.assertEqual(record.reported_model_version, "gemini-2.5-flash")
            self.assertEqual(record.token_usage["totalTokenCount"], 15)
            self.assertNotIn("ignored", record.token_usage)
            self.assertNotIn("fixture-secret-key", record.model_dump_json())
            self.assertNotIn("fixture-secret-key", json.dumps(configuration_status()))

    def test_429_retries_once_then_succeeds(self):
        error = HTTPError("https://example.invalid", 429, "fixture-secret-key", {}, io.BytesIO(b"secret response"))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), patch("firewatch.gateway.time.sleep"), \
             patch("firewatch.gateway.urlopen", side_effect=[error, Response({"status": "ok"})]) as network:
            record = check_gemini()
            self.assertEqual(network.call_count, 2)
            self.assertEqual([a.status for a in record.attempts], ["HTTP_ERROR", "SUCCESS"])
            self.assertEqual(record.attempts[0].http_status, 429)
            self.assertNotIn("secret", record.model_dump_json())

    def test_400_is_not_retried_and_raw_error_is_hidden(self):
        error = HTTPError("https://example.invalid", 400, "secret message", {}, io.BytesIO(b"private"))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), patch("firewatch.gateway.urlopen", side_effect=error) as network:
            record = check_gemini()
            self.assertFalse(record.succeeded)
            self.assertEqual(record.error_code, "HTTP_400")
            self.assertEqual(network.call_count, 1)
            self.assertNotIn("secret", record.model_dump_json())

    def test_timeout_retry_limit(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), patch("firewatch.gateway.time.sleep"), \
             patch("firewatch.gateway.urlopen", side_effect=TimeoutError("secret key")) as network:
            record = check_gemini()
            self.assertEqual(network.call_count, 2)
            self.assertEqual(record.error_code, "NETWORK_ERROR")
            self.assertFalse(record.succeeded)
            self.assertNotIn("secret", record.model_dump_json())

    def test_invalid_structured_output_is_not_retried(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), \
             patch("firewatch.gateway.urlopen", return_value=Response({"bogus": "wrong schema"})) as network:
            record = check_gemini()
            self.assertEqual(record.error_code, "INVALID_OUTPUT")
            self.assertEqual(network.call_count, 1)

    def test_truncated_response_cannot_count_as_validated(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), \
             patch("firewatch.gateway.urlopen", return_value=Response({"status": "ok"}, finish="MAX_TOKENS")):
            record = check_gemini()
            self.assertFalse(record.output_validated)
            self.assertEqual(record.attempts[0].status, "BLOCKED")

    def test_probe_excludes_incident_observations(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), \
             patch("firewatch.gateway.urlopen", return_value=Response({"status": "ok"})) as network:
            check_gemini()
            request = network.call_args.args[0]
            context = json.loads(json.loads(request.data)["contents"][0]["parts"][0]["text"])
            self.assertEqual(context, {"configuration_probe": True, "incident_data_included": False})
            self.assertNotIn("fixture-secret-key", request.full_url)

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({"model": "invalid/model"}, {"attempts": 3}, {"attempts": True},
                       {"timeout": float("nan")}, {"timeout": 0}, {"timeout": 61}):
            with self.subTest(kwargs=kwargs), self.assertRaises(GatewayError): GeminiGateway(**kwargs)

    def test_provider_probe_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), \
             patch("firewatch.gateway.urlopen", return_value=Response({"status": "ok"})):
            record = check_gemini(store=Store(directory))
            restored = Store(directory).latest_provider_check()
            self.assertEqual(restored, record)
            self.assertNotIn("fixture-secret-key", restored.model_dump_json())


class ReviewGateway:
    """Offline routing fixture. Explicitly recorded as injected_gateway."""
    def __init__(self, request_from="Critic", revise=False):
        self.request_from, self.revise = request_from, revise
        self.decision_calls = 0
        self.critic_calls = 0
    def call(self, component, schema, context):
        if component == "Planner":
            return Plan(tool="assess_evidence", rationale="Fixture route", human_review=self.request_from == "Planner")
        if component == "Decision":
            self.decision_calls += 1
            return Proposal(assessment_status=context["assessment"]["status"], risk_level=context["risk"]["level"],
                            human_review=self.request_from == "Decision" and self.decision_calls == 1,
                            rationale="Fixture proposal", questions=[], evidence_ids=context["evidence"]["evidence_ids"])
        self.critic_calls += 1
        return CriticReview(verdict="REVISE" if self.revise and self.critic_calls == 1 else "APPROVE",
                            reasons=["Fixture revision"] if self.revise and self.critic_calls == 1 else [],
                            human_review=self.request_from == "Critic" and self.critic_calls == 1)


class PipelineV4Tests(unittest.TestCase):
    def test_full_hybrid_flow_with_mocked_http(self):
        def provider(request, timeout):
            payload = json.loads(request.data)
            component = payload["systemInstruction"]["parts"][0]["text"].rsplit(": ", 1)[-1]
            context = json.loads(payload["contents"][0]["parts"][0]["text"])
            if component == "Planner":
                output = {"tool": "assess_evidence", "rationale": "Mocked route", "human_review": False}
            elif component == "Decision":
                output = {"assessment_status": context["assessment"]["status"], "risk_level": context["risk"]["level"],
                          "human_review": False, "rationale": "Mocked proposal", "questions": [],
                          "evidence_ids": context["evidence"]["evidence_ids"]}
            else:
                output = {"verdict": "APPROVE", "reasons": [], "human_review": True}
            return Response(output)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-secret-key"}), patch("firewatch.gateway.urlopen", side_effect=provider) as network:
            result = Pipeline().run(sample("HTTP flow", smoke="no", flames="no", exposure="no"), use_llm=True)
            self.assertEqual(network.call_count, 3)
            self.assertEqual(result.mode, "llm")
            self.assertTrue(all(call.source == "gemini_api" and call.output_validated for call in result.llm_calls))
            self.assertTrue(result.safety.human_review_required)
            self.assertNotIn("fixture-secret-key", result.model_dump_json())

    def test_review_request_survives_semantically_rejected_proposal(self):
        class RejectedProposalGateway(ReviewGateway):
            def call(self, component, schema, context):
                response = super().call(component, schema, context)
                if component == "Decision" and self.decision_calls == 1:
                    response.assessment_status = "STRONG_INDICATION"
                return response
        result = Pipeline(RejectedProposalGateway("Decision")).run(
            sample("Complete", smoke="no", flames="no", exposure="no"), use_llm=True)
        self.assertEqual(result.critic.verdict, "APPROVE")
        self.assertEqual(result.assessment.status, "NO_INDICATION")
        self.assertFalse(result.proposal.human_review)
        self.assertTrue(result.safety.human_review_required)
        self.assertTrue(result.llm_review_requests)

    def test_approved_critic_request_reaches_safety(self):
        incident = sample("Complete", smoke="no", flames="no", exposure="no")
        result = Pipeline(ReviewGateway()).run(incident, use_llm=True)
        self.assertEqual(result.critic.verdict, "APPROVE")
        self.assertFalse(result.proposal.human_review)
        self.assertTrue(result.safety.human_review_required)
        self.assertIn("Critic LLM requested", " ".join(result.safety.reasons))

    def test_requests_survive_revision_for_each_component(self):
        for component in ("Planner", "Decision", "Critic"):
            with self.subTest(component=component):
                result = Pipeline(ReviewGateway(component, revise=True)).run(
                    sample("Complete", smoke="no", flames="no", exposure="no"), use_llm=True)
                self.assertEqual(result.revisions, 1)
                self.assertFalse(result.proposal.human_review)
                self.assertFalse(result.critic.human_review)
                self.assertTrue(result.safety.human_review_required)
                self.assertTrue(any(component in reason for reason in result.llm_review_requests))

    def test_injected_gateway_is_not_reported_as_provider_access(self):
        result = Pipeline(ReviewGateway()).run(sample("Fixture"), use_llm=True)
        self.assertTrue(result.llm_calls)
        self.assertTrue(all(call.source == "injected_gateway" for call in result.llm_calls))

    def test_missing_key_fallback_audit_and_review(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}), patch("firewatch.gateway.urlopen") as network:
            result = Pipeline().run(sample("Complete", smoke="no", flames="no", exposure="no"), use_llm=True)
            self.assertEqual(result.mode, "fallback")
            self.assertEqual(result.llm_calls[0].error_code, "MISSING_KEY")
            self.assertTrue(result.safety.human_review_required)
            network.assert_not_called()

    def test_deterministic_run_does_not_create_provider_calls(self):
        with patch("firewatch.gateway.urlopen") as network:
            result = Pipeline().run(sample("Reference"))
            self.assertEqual(result.llm_calls, [])
            self.assertEqual(result.llm_review_requests, [])
            network.assert_not_called()

    def test_audit_and_requests_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Pipeline(ReviewGateway(revise=True)).run(sample("Persist"), use_llm=True)
            store = Store(directory)
            store.save(result)
            restored = store.load(result.run_id)
            self.assertEqual(restored.llm_calls, result.llm_calls)
            self.assertEqual(restored.llm_review_requests, result.llm_review_requests)


if __name__ == "__main__":
    unittest.main()
