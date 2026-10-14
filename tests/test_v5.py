import csv
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from firewatch.context import context_agent
from firewatch.models import (EvaluationDecision, FireContext, HumanAssessment, HumanReview,
                              Incident, RunResult, SharedState, ShadowDataset, ShadowAnalysis)
from firewatch.pipeline import Pipeline
from firewatch.research import human_comparison, human_comparison_csv, project_shadow, run_shadow
from firewatch.scenarios import sample
from firewatch.storage import Store
from firewatch.v5_demo import shadow_demo


AT = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)


class ContextTests(unittest.TestCase):
    def test_numeric_context_rejects_invalid_values(self):
        for field, value in [("slope_deg", 91), ("gust_kmh", -1), ("distance_to_people_m", -1),
                             ("distance_to_infrastructure_m", float("nan"))]:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                FireContext(**{field: value})

    def test_dry_context_never_creates_fire_indicator(self):
        incident = sample("Dry context", smoke="no", flames="no", exposure="no")
        incident.context = FireContext(fuel_type="grass", slope_deg=45, gust_kmh=90)
        incident.context_evidence_ids = [incident.evidence[0].id]
        result = Pipeline().run(incident)
        self.assertEqual(result.assessment.status, "NO_INDICATION")
        self.assertEqual(result.risk.level, "LOW")
        self.assertFalse(result.safety.human_review_required)
        self.assertEqual(result.context_result.values.gust_kmh, 90)

    def test_context_exposure_inconsistency_requires_review(self):
        incident = sample("Conflict", smoke="no", flames="no", exposure="no")
        incident.context = FireContext(people_present="yes")
        incident.context_evidence_ids = [incident.evidence[0].id]
        result = Pipeline().run(incident)
        self.assertEqual(result.assessment.status, "NO_INDICATION")
        self.assertTrue(result.safety.human_review_required)
        self.assertTrue(any("reconcile" in r for r in result.safety.reasons))

    def test_restricted_access_retains_review_and_no_commands(self):
        incident = sample("Blocked", smoke="yes", flames="no", exposure="no")
        incident.context = FireContext(access_status="blocked")
        incident.context_evidence_ids = [incident.evidence[0].id]
        result = Pipeline().run(incident)
        self.assertTrue(any("restricted access" in r for r in result.safety.reasons))
        self.assertEqual(result.risk.level, "MEDIUM")

    def test_unlinked_context_is_flagged_but_unknown_is_preserved(self):
        incident = sample("Unlinked")
        incident.context = FireContext(wind_direction="NE")
        analysis = context_agent(incident)
        self.assertTrue(analysis.human_review_required)
        self.assertEqual(analysis.values.people_present, "unknown")
        self.assertIsNone(analysis.values.distance_to_people_m)

    def test_context_cannot_cite_nonexistent_evidence(self):
        data = sample("Invented citation").model_dump()
        data["context_evidence_ids"] = ["invented"]
        with self.assertRaises(ValidationError): Incident.model_validate(data)

    def test_context_is_in_report_trace_state_and_restored_run(self):
        incident = sample("Persistence", smoke="yes")
        incident.context = FireContext(fuel_type="forest", slope_deg=12)
        incident.context_evidence_ids = [incident.evidence[0].id]
        result = Pipeline().run(incident)
        self.assertIn('"slope_deg": 12.0', result.report)
        self.assertTrue(any(e.component == "Context" for e in result.trace))
        self.assertEqual(SharedState.from_run(result).context_result, result.context_result)
        self.assertEqual(result.graph_steps[0].state["context_result"]["values"]["fuel_type"], "forest")
        with tempfile.TemporaryDirectory() as d:
            Store(d).save(result)
            self.assertEqual(Store(d).load(result.run_id).context_result, result.context_result)

    def test_v4_snapshot_loads_with_unknown_context(self):
        payload = Pipeline().run(sample("Legacy")).model_dump(mode="json")
        payload.pop("context_result")
        payload["incident"].pop("context")
        payload["incident"].pop("context_evidence_ids")
        restored = RunResult.model_validate(payload)
        self.assertIsNone(restored.context_result)
        self.assertEqual(restored.incident.context, FireContext())


class HumanComparisonTests(unittest.TestCase):
    def setUp(self):
        self.result = Pipeline().run(sample("Human", smoke="yes", flames="yes", exposure="yes"))

    def judgment(self, **updates):
        values = dict(run_id=self.result.run_id, reviewer="Test reviewer", rationale="Entered test judgment, not a real human evaluation",
                      decision=EvaluationDecision(assessment="STRONG_INDICATION", risk="HIGH", human_review=True),
                      system_output_seen=True)
        values.update(updates)
        return HumanAssessment(**values)

    def test_no_human_records_does_not_invent_baseline(self):
        data = human_comparison(self.result, [])
        self.assertEqual(data["status"], "NOT_RECORDED")
        self.assertEqual(data["reviewers_compared"], 0)
        self.assertEqual(data["rows"], [])

    def test_human_judgment_requires_explicit_seen_flag_and_nonblank_name(self):
        for updates in [{"system_output_seen": "false"}, {"reviewer": "  "}, {"rationale": "  "}]:
            with self.subTest(updates=updates), self.assertRaises(ValidationError): self.judgment(**updates)
        payload = self.judgment().model_dump()
        payload.pop("system_output_seen")
        with self.assertRaises(ValidationError): HumanAssessment.model_validate(payload)

    def test_disagreement_counts_and_original_safety_preserved(self):
        judgment = self.judgment(decision=EvaluationDecision(assessment="NO_INDICATION", risk="LOW", human_review=False))
        data = human_comparison(self.result, [judgment])
        self.assertEqual(data["all_fields_agree"], 0)
        self.assertEqual(data["extra_reviews"], 1)
        self.assertEqual(data["missed_reviews"], 0)
        self.assertTrue(self.result.safety.human_review_required)
        self.assertFalse(data["rows"][0]["field_agreement"]["risk"])

    def test_missing_review_uses_entered_human_denominator(self):
        result = Pipeline().run(sample("No indicators", smoke="no", flames="no", exposure="no"))
        judgment = self.judgment(run_id=result.run_id)
        data = human_comparison(result, [judgment])
        self.assertEqual(data["reviewers_compared"], 1)
        self.assertEqual(data["missed_reviews"], 1)

    def test_latest_entry_per_reviewer_avoids_double_counting(self):
        first = self.judgment(recorded_at=self.result.created_at + timedelta(seconds=1))
        second = self.judgment(recorded_at=first.recorded_at + timedelta(seconds=1), reviewer="TEST REVIEWER")
        data = human_comparison(self.result, [second, first])
        self.assertEqual(data["reviewers_compared"], 1)
        self.assertEqual(data["rows"][0]["assessment_id"], second.assessment_id)

    def test_comparison_rejects_wrong_run(self):
        with self.assertRaises(ValueError): human_comparison(self.result, [self.judgment(run_id="other")])

    def test_baseline_requires_saved_run_and_survives_restart_separate_from_approval(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            with self.assertRaises(ValueError): store.save_human_assessment(self.judgment())
            store.save(self.result)
            with self.assertRaises(ValueError):
                store.save_human_assessment(self.judgment(recorded_at=self.result.created_at - timedelta(seconds=1)))
            store.review(HumanReview(run_id=self.result.run_id, reviewer="Test reviewer", decision="APPROVED", comment="Test approval"))
            self.assertEqual(store.human_assessments(self.result.run_id), [])
            judgment = self.judgment()
            store.save_human_assessment(judgment)
            restarted = Store(d)
            self.assertEqual(restarted.human_assessments(self.result.run_id), [judgment])
            self.assertEqual(restarted.load(self.result.run_id).safety, self.result.safety)

    def test_csv_retains_link_and_output_seen_disclosure(self):
        judgment = self.judgment()
        data = human_comparison(self.result, [judgment])
        row = next(csv.DictReader(io.StringIO(human_comparison_csv(data))))
        self.assertEqual(row["run_id"], self.result.run_id)
        self.assertEqual(row["assessment_id"], judgment.assessment_id)
        self.assertEqual(row["system_output_seen"], "True")
        self.assertEqual(row["all_fields_agree"], "True")


class ShadowTests(unittest.TestCase):
    def test_saved_shadow_rejects_mismatched_audit_and_provider_mode(self):
        original = run_shadow(shadow_demo(), AT).model_dump(mode="json")
        for change in ("ids", "cutoff", "mode"):
            payload = json.loads(json.dumps(original))
            if change == "ids": payload["audit"]["included_ids"] = ["invented"]
            elif change == "cutoff": payload["audit"]["cutoff"] = "2026-10-14T13:00:00Z"
            else: payload["result"]["mode"] = "llm"
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ShadowAnalysis.model_validate(payload)

    def test_json_example_retains_partial_updates(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "v5-shadow-synthetic.json"
        dataset = ShadowDataset.model_validate_json(path.read_text())
        incident, _ = project_shadow(dataset, AT)
        self.assertEqual(incident.flames, "no")
        self.assertEqual(incident.smoke, "no")
        self.assertEqual(incident.context.slope_deg, 15)

    def test_cutoff_blocks_late_text_fields_and_unknown_availability(self):
        dataset = shadow_demo()
        incident, audit = project_shadow(dataset, AT)
        self.assertEqual(audit.dataset_id, dataset.dataset_id)
        self.assertEqual(audit.included_ids, ["demo-early", "demo-context"])
        self.assertEqual(audit.excluded["demo-late"], ["available_after_cutoff"])
        self.assertEqual(audit.excluded["demo-unknown-availability"], ["availability_unknown"])
        self.assertEqual(incident.flames, "no")
        self.assertNotIn("arrived only after", incident.model_dump_json())
        self.assertEqual(audit.field_evidence_ids["flames"], ["demo-early"])
        self.assertEqual(audit.field_evidence_ids["context.gust_kmh"], ["demo-context"])

    def test_partial_context_update_does_not_reset_indicators(self):
        incident, _ = project_shadow(shadow_demo(), AT)
        self.assertEqual((incident.smoke, incident.flames, incident.exposure), ("no", "no", "no"))
        self.assertEqual(incident.humidity_pct, 20)
        self.assertEqual(incident.context.gust_kmh, 40)

    def test_later_cutoff_admits_report_changes_result_with_new_ids(self):
        first = run_shadow(shadow_demo(), AT)
        later = run_shadow(shadow_demo(), AT + timedelta(hours=1))
        self.assertEqual(first.result.assessment.status, "NO_INDICATION")
        self.assertEqual(later.result.assessment.status, "STRONG_INDICATION")
        self.assertEqual(later.result.risk.level, "HIGH")
        self.assertTrue(later.result.safety.human_review_required)
        self.assertNotEqual(first.result.run_id, later.result.run_id)

    def test_observed_after_cutoff_is_excluded_even_if_availability_claim_is_early(self):
        dataset = shadow_demo()
        dataset.records[2].available_at = AT
        dataset.records[2].evidence.observed_at = AT + timedelta(seconds=1)
        _, audit = project_shadow(dataset, AT)
        self.assertEqual(audit.excluded["demo-late"], ["observed_after_cutoff"])

    def test_exact_cutoff_included_and_timezone_equivalence(self):
        dataset = shadow_demo()
        dataset.records[2].available_at = AT
        dataset.records[2].evidence.observed_at = AT
        incident, audit = project_shadow(dataset, AT.astimezone(timezone(timedelta(hours=-3))))
        self.assertIn("demo-late", audit.included_ids)
        self.assertEqual(incident.flames, "yes")

    def test_no_eligible_records_and_naive_cutoff_block_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            with self.assertRaises(ValueError): run_shadow(shadow_demo(), AT - timedelta(days=1), store=store)
            self.assertEqual(store.recent(), [])
        with self.assertRaises(ValueError): project_shadow(shadow_demo(), AT.replace(tzinfo=None))

    def test_tied_conflicting_normalized_fields_become_unknown_and_require_review(self):
        dataset = shadow_demo()
        dataset.records[2].available_at = AT
        dataset.records[2].evidence.observed_at = dataset.records[0].evidence.observed_at
        analysis = run_shadow(dataset, AT)
        self.assertEqual(analysis.result.incident.flames, "unknown")
        self.assertIn("flames", analysis.audit.conflicting_fields)
        self.assertTrue(analysis.result.evidence_result.conflicts)
        self.assertTrue(analysis.result.safety.human_review_required)

    def test_explicit_unknown_update_is_not_dropped(self):
        payload = shadow_demo().model_dump(mode="json")
        payload["records"][1]["values"] = {"flames": "unknown"}
        incident, _ = project_shadow(payload, AT)
        self.assertEqual(incident.flames, "unknown")

    def test_shadow_is_offline_and_history_contains_cutoff_policy(self):
        with tempfile.TemporaryDirectory() as d, patch("firewatch.gateway.urlopen") as network:
            analysis = run_shadow(shadow_demo(), AT, store=Store(d))
            network.assert_not_called()
            self.assertEqual(analysis.result.llm_calls, [])
            self.assertEqual(analysis.result.created_at, AT)
            restarted = Store(d)
            restored = restarted.load_shadow(analysis.shadow_id)
            self.assertEqual(restored, analysis)
            self.assertEqual(restarted.load(analysis.result.run_id).trace[0].component, "ShadowPolicy")
            self.assertEqual(restored.audit.cutoff, AT)
            self.assertIn("SHADOW MODE", restored.result.report)

    def test_shadow_input_rejects_duplicate_ids_and_naive_availability(self):
        payload = shadow_demo().model_dump(mode="json")
        payload["records"][1]["evidence"]["id"] = payload["records"][0]["evidence"]["id"]
        with self.assertRaises(ValidationError): ShadowDataset.model_validate(payload)
        payload = shadow_demo().model_dump(mode="json")
        payload["records"][0]["available_at"] = "2026-10-14T11:00:00"
        with self.assertRaises(ValidationError): ShadowDataset.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
