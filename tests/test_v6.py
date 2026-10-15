import contextlib
import csv
import hashlib
import io
import json
import os
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

import main
from firewatch.bundle import comparison_bundle
from firewatch.comparison import (compare, comparison_csv, comparison_metrics, comparison_report,
                                  incident_hash, integrity_issues, validate_comparison)
from firewatch.models import ComparativeEvaluation, HumanReview
from firewatch.pipeline import Pipeline
from firewatch.storage import Store
from test_v4 import Response, ReviewGateway


class ComparisonTests(unittest.TestCase):
    def test_offline_all_cases_preserve_twenty_pair_labels_with_zero_network(self):
        with patch("firewatch.gateway.urlopen") as network:
            evaluation = compare(repetitions=2)
        self.assertEqual(evaluation.metrics.pairs, 20)
        self.assertEqual(evaluation.metrics.final_decision_agreement, 20)
        self.assertEqual(evaluation.metrics.candidate_label_matches, 20)
        self.assertEqual(evaluation.metrics.fully_validated_provider_pairs, 0)
        self.assertEqual(evaluation.metrics.provider_http_attempts, 0)
        self.assertEqual(evaluation.metrics.candidate_modes, {"deterministic": 20})
        self.assertEqual(evaluation.metrics.intact_runs, 40)
        self.assertEqual(evaluation.metrics.candidate_stable_cases, 10)
        network.assert_not_called()

    def test_pairs_share_input_time_and_checksum_but_distinct_ids(self):
        evaluation = compare(scenario_numbers=[3], repetitions=2)
        ids = []
        for row in evaluation.rows:
            self.assertEqual(row.reference.incident, row.candidate.incident)
            self.assertEqual(row.reference.created_at, row.candidate.created_at)
            self.assertEqual(row.input_sha256, incident_hash(row.candidate.incident))
            ids.extend([row.reference.run_id, row.candidate.run_id])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(evaluation.rows[0].input_sha256, evaluation.rows[1].input_sha256)

    def test_invalid_protocol_arguments_are_rejected(self):
        for repetitions in (True, 0, 4, 1.5):
            with self.subTest(repetitions=repetitions), self.assertRaises(ValueError):
                compare(repetitions=repetitions)
        for numbers in ([], [1, 1], [0], [11], [True]):
            with self.subTest(numbers=numbers), self.assertRaises(ValueError):
                compare(scenario_numbers=numbers)

    def test_single_trial_does_not_claim_reproducibility(self):
        evaluation = compare(scenario_numbers=[3], repetitions=1)
        self.assertEqual(evaluation.metrics.repeated_cases_checked, 0)
        self.assertEqual(evaluation.metrics.candidate_stable_cases, 0)

    def test_injected_reasoning_is_not_counted_as_provider_validation(self):
        evaluation = compare(use_llm=True, scenario_numbers=[1], repetitions=2,
                             pipeline_factory=lambda: Pipeline(ReviewGateway()))
        self.assertEqual(evaluation.metrics.candidate_modes, {"llm": 2})
        self.assertEqual(evaluation.metrics.fully_validated_provider_pairs, 0)
        self.assertEqual(evaluation.metrics.source_call_counts, {"injected_gateway": 6})
        self.assertEqual(evaluation.metrics.candidate_more_reviews, 2)
        self.assertEqual(evaluation.metrics.final_decision_agreement, 0)
        self.assertEqual(evaluation.metrics.candidate_removed_reviews, 0)
        self.assertEqual(evaluation.metrics.candidate_label_matches, 0)

    def test_proposal_differences_are_separate_from_final_safety_decisions(self):
        evaluation = compare(use_llm=True, scenario_numbers=[1], repetitions=1,
                             pipeline_factory=lambda: Pipeline(ReviewGateway("Decision", revise=True)))
        row = evaluation.rows[0]
        self.assertFalse(row.candidate.proposal.human_review)
        self.assertTrue(row.candidate.safety.human_review_required)
        self.assertEqual(evaluation.metrics.final_decision_agreement, 0)
        self.assertEqual(evaluation.metrics.candidate_proposal_differences, 0)
        self.assertEqual(row.candidate.revisions, 1)

    def test_missing_key_comparison_records_fallback_and_zero_http(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}), patch("firewatch.gateway.urlopen") as network:
            evaluation = compare(use_llm=True, scenario_numbers=[3], repetitions=1)
        network.assert_not_called()
        self.assertEqual(evaluation.metrics.candidate_modes, {"fallback": 1})
        self.assertEqual(evaluation.metrics.candidate_error_codes, {"MISSING_KEY": 1})
        self.assertEqual(evaluation.metrics.provider_http_attempts, 0)
        self.assertEqual(evaluation.metrics.fully_validated_provider_pairs, 0)
        self.assertEqual(evaluation.requested_candidate, "gemini_hybrid")

    def test_mocked_provider_audits_count_components_attempts_and_tokens(self):
        # Mocked transport contract, NOT evidence of a live Gemini request.
        def transport(request, timeout):
            payload = json.loads(request.data)
            component = payload["systemInstruction"]["parts"][0]["text"].rsplit(": ", 1)[-1]
            context = json.loads(payload["contents"][0]["parts"][0]["text"])
            if component == "Planner":
                output = {"tool": "assess_evidence", "rationale": "Offline fixture", "human_review": False}
            elif component == "Decision":
                output = {"assessment_status": context["assessment"]["status"], "risk_level": context["risk"]["level"],
                          "human_review": True, "rationale": "Offline fixture", "questions": [],
                          "evidence_ids": context["evidence"]["evidence_ids"]}
            else:
                output = {"verdict": "APPROVE", "reasons": [], "human_review": True}
            return Response(output)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-fixture-secret"}), patch("firewatch.gateway.urlopen", side_effect=transport) as network:
            evaluation = compare(use_llm=True, scenario_numbers=[3], repetitions=1)
        self.assertEqual(network.call_count, 3)
        self.assertEqual(evaluation.metrics.fully_validated_provider_pairs, 1)
        self.assertEqual(evaluation.metrics.provider_http_attempts, 3)
        self.assertEqual(evaluation.metrics.provider_token_usage["totalTokenCount"], 45)
        self.assertNotIn("offline-fixture-secret", evaluation.model_dump_json())

    def test_provider_pair_requires_all_three_components(self):
        evaluation = compare(scenario_numbers=[3], repetitions=1)
        run = evaluation.rows[0].candidate
        from firewatch.models import LLMCallRecord
        run.mode = "llm"
        run.llm_calls = [LLMCallRecord(component="Planner", requested_model="fixture", source="gemini_api", succeeded=True, output_validated=True)]
        self.assertEqual(comparison_metrics(evaluation.rows).fully_validated_provider_pairs, 0)

    def test_cancel_before_start_saves_explicit_empty_cancelled_result(self):
        stop = threading.Event()
        stop.set()
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            evaluation = compare(store, cancel_event=stop)
            self.assertEqual(evaluation.status, "CANCELLED")
            self.assertEqual(evaluation.metrics.pairs, 0)
            self.assertEqual(store.recent(), [])
            self.assertEqual(store.load_comparison(evaluation.comparison_id), evaluation)

    def test_cancel_after_pair_preserves_partial_history_and_progress(self):
        stop, progress = threading.Event(), []
        def callback(data):
            progress.append(data)
            stop.set()
        evaluation = compare(scenario_numbers=[1, 3], repetitions=2, cancel_event=stop, on_progress=callback)
        self.assertEqual(evaluation.status, "CANCELLED")
        self.assertEqual(evaluation.metrics.pairs, 1)
        self.assertEqual(progress[0]["completed_pairs"], 1)
        self.assertEqual(progress[0]["requested_pairs"], 4)

    def test_restart_restores_comparison_and_both_original_runs(self):
        with tempfile.TemporaryDirectory() as d:
            evaluation = compare(Store(d), scenario_numbers=[3], repetitions=2)
            restarted = Store(d)
            self.assertEqual(restarted.load_comparison(evaluation.comparison_id), evaluation)
            for row in evaluation.rows:
                self.assertEqual(restarted.load(row.reference.run_id), row.reference)
                self.assertEqual(restarted.load(row.candidate.run_id), row.candidate)

    def test_store_rejects_comparison_without_original_runs(self):
        evaluation = compare(scenario_numbers=[3], repetitions=1)
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            Store(d).save_comparison(evaluation)

    def test_input_changes_are_detected_and_not_paired_silently(self):
        class ChangedPipeline:
            def run(self, incident, **kwargs):
                incident.location = "Changed input"
                return Pipeline().run(incident, **kwargs)
        with self.assertRaises(ValueError):
            compare(scenario_numbers=[3], repetitions=1, pipeline_factory=ChangedPipeline)

    def test_tampered_summary_metrics_and_checksum_are_rejected(self):
        evaluation = compare(scenario_numbers=[3], repetitions=1)
        payload = evaluation.model_dump(mode="json")
        payload["metrics"]["fully_validated_provider_pairs"] = 1
        with self.assertRaises(ValueError): validate_comparison(payload)

    def test_changed_inputs_between_repetitions_cannot_claim_repeatability(self):
        evaluation = compare(scenario_numbers=[3], repetitions=2)
        payload = evaluation.model_dump(mode="json")
        row = payload["rows"][1]
        for key in ("reference", "candidate"):
            row[key]["incident"]["location"] = "Changed between repetitions"
        from firewatch.models import Incident
        row["input_sha256"] = incident_hash(Incident.model_validate(row["reference"]["incident"]))
        with self.assertRaises(ValueError): validate_comparison(payload)
        payload = evaluation.model_dump(mode="json")
        payload["rows"][0]["input_sha256"] = "0" * 64
        with self.assertRaises(ValueError): validate_comparison(payload)

    def test_incomplete_duplicate_or_different_time_pairs_are_rejected(self):
        evaluation = compare(scenario_numbers=[3], repetitions=2)
        payload = evaluation.model_dump(mode="json")
        payload["rows"] = payload["rows"][:1]
        with self.assertRaises(ValidationError): ComparativeEvaluation.model_validate(payload)
        payload = evaluation.model_dump(mode="json")
        payload["rows"][1] = payload["rows"][0]
        with self.assertRaises(ValidationError): ComparativeEvaluation.model_validate(payload)
        payload = evaluation.model_dump(mode="json")
        payload["rows"][0]["candidate"]["created_at"] = "2020-01-01T00:00:00Z"
        with self.assertRaises(ValidationError): ComparativeEvaluation.model_validate(payload)

    def test_invalid_trace_and_citation_reduce_integrity_counts(self):
        evaluation = compare(scenario_numbers=[3], repetitions=1)
        run = evaluation.rows[0].candidate
        run.trace[0].run_id = "wrong"
        run.proposal.evidence_ids = ["invented"]
        run.graph_steps[0].run_id = "wrong"
        issues = integrity_issues(run)
        self.assertGreaterEqual(len(issues), 3)
        self.assertEqual(comparison_metrics(evaluation.rows).intact_runs, 1)

    def test_csv_and_txt_preserve_actual_modes_and_run_links(self):
        evaluation = compare(scenario_numbers=[3], repetitions=1)
        row = next(csv.DictReader(io.StringIO(comparison_csv(evaluation))))
        self.assertEqual(row["reference_run_id"], evaluation.rows[0].reference.run_id)
        self.assertEqual(row["candidate_run_id"], evaluation.rows[0].candidate.run_id)
        self.assertEqual(row["requested_candidate"], "deterministic_replay")
        self.assertEqual(row["actual_candidate_mode"], "deterministic")
        report = comparison_report(evaluation)
        self.assertIn("Fully validated provider pairs: 0/1", report)
        self.assertIn("not fire accuracy", report)


class BundleTests(unittest.TestCase):
    def test_bundle_manifest_checksums_trace_links_and_human_records(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            evaluation = compare(store, scenario_numbers=[3], repetitions=1)
            candidate = evaluation.rows[0].candidate
            store.review(HumanReview(run_id=candidate.run_id, reviewer="Automated fixture", decision="APPROVED", comment="Fixture only"))
            with zipfile.ZipFile(io.BytesIO(comparison_bundle(evaluation, store))) as archive:
                self.assertIsNone(archive.testzip())
                manifest = json.loads(archive.read("manifest.json"))
                for filename, digest in manifest["sha256"].items():
                    self.assertEqual(hashlib.sha256(archive.read(filename)).hexdigest(), digest)
                traces = [json.loads(line) for line in archive.read("trace.jsonl").decode().splitlines()]
                self.assertEqual({t["run_id"] for t in traces}, set(manifest["run_ids"]))
                exported = [json.loads(archive.read(name)) for name in archive.namelist() if name.startswith("runs/")]
                current = next(r for r in exported if r["run_id"] == candidate.run_id)
                self.assertEqual(len(current["human_reviews"]), 1)
                self.assertEqual(current["human_comparison"]["status"], "NOT_RECORDED")
                self.assertTrue(current["safety"]["human_review_required"])

    def test_bundle_rejects_mismatched_saved_run(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            evaluation = compare(store, scenario_numbers=[3], repetitions=1)
            with store.connect() as db:
                db.execute("DELETE FROM runs WHERE id=?", (evaluation.rows[0].candidate.run_id,))
            with self.assertRaises(KeyError): comparison_bundle(evaluation, store)

    def test_legacy_evidence_snapshots_still_load_under_v6(self):
        from firewatch.models import RunResult
        root = Path(__file__).resolve().parents[1]
        data = json.loads((root / "docs/evidence/windows-2026-10-14/v4-gemini-case03.json").read_text(encoding="utf-8"))
        data.pop("human_reviews", None)
        run = RunResult.model_validate(data)
        self.assertEqual(run.mode, "llm")
        self.assertEqual(run.incident.context.model_dump()["fuel_type"], "unknown")
        self.assertEqual(integrity_issues(run), [])


class V6CommandTests(unittest.TestCase):
    def invoke(self, args):
        with patch("sys.argv", ["main.py", *args]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main.main()

    def test_cli_exports_full_dossier_without_provider(self):
        with tempfile.TemporaryDirectory() as d, patch("firewatch.gateway.urlopen") as network:
            root = Path(d)
            args = ["--compare", "--compare-cases", "3", "--repetitions", "1", "--data-dir", d,
                    "--output", str(root/"comparison.json"), "--csv", str(root/"comparison.csv"),
                    "--report", str(root/"report.txt"), "--bundle", str(root/"evidence.zip")]
            self.assertEqual(self.invoke(args), 0)
            self.assertEqual(validate_comparison(json.loads((root/"comparison.json").read_text(encoding="utf-8"))).metrics.pairs, 1)
            self.assertTrue((root/"comparison.csv").exists())
            self.assertNotIn(b"\r\r\n", (root/"comparison.csv").read_bytes())
            self.assertTrue(zipfile.is_zipfile(root/"evidence.zip"))
            network.assert_not_called()

    def test_cli_hybrid_fallback_has_nonzero_provider_validation_exit(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"GEMINI_API_KEY": ""}), patch("firewatch.gateway.urlopen") as network:
            self.assertEqual(self.invoke(["--compare", "--compare-cases", "3", "--repetitions", "1", "--llm", "--data-dir", d]), 2)
            network.assert_not_called()

    def test_cli_conflicting_modes_and_inapplicable_options_are_rejected(self):
        for args in (["--compare", "--shadow-demo"], ["--compare", "--evaluate"],
                     ["--compare", "--repetitions", "5"], ["--report", "report.txt"],
                     ["--compare-cases", "3"], ["--evaluate", "--repetitions", "1"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as raised:
                self.invoke(args)
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
