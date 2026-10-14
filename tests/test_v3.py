import csv
import io
import json
import tempfile
import unittest

from firewatch.evaluation import aggregate_metrics, agreements, evaluate, evaluation_csv
from firewatch.models import EvaluationCase, EvaluationDecision, PilotEvaluation
from firewatch.pipeline import Pipeline
from firewatch.storage import Store


class V3PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = evaluate()

    def test_label_comparison_and_baseline_are_separate(self):
        metrics = self.data["metrics"]
        self.assertEqual(metrics["system_case_matches"], 10)
        self.assertEqual(metrics["baseline_case_matches"], 7)
        self.assertEqual(metrics["baseline_missed_reviews"], 1)
        self.assertEqual(metrics["system_missed_reviews"], 0)
        self.assertIn("not observed human judgment", self.data["limitation"])

    def test_repeated_runs_preserve_decisions_with_unique_ids(self):
        rows = self.data["rows"]
        self.assertTrue(all(row["reproducible"] for row in rows))
        ids = [trial["run_id"] for row in rows for trial in row["trials"]]
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(set(ids)), 20)
        self.assertEqual(self.data["metrics"]["valid_trace_run_ids"], 20)

    def test_decision_drift_is_detected(self):
        calls = 0
        class DriftingPipeline:
            def run(self, incident, at=None):
                nonlocal calls
                calls += 1
                result = Pipeline().run(incident, at=at)
                if calls % 2 == 0:
                    result.risk.level = "LOW" if result.risk.level != "LOW" else "HIGH"
                return result
        data = evaluate(pipeline_factory=DriftingPipeline)
        self.assertEqual(data["metrics"]["reproducible_cases"], 0)
        self.assertEqual(data["passed"], 10)  # First-trial label agreement is not repetition stability.

    def test_bad_citations_and_trace_ids_are_detected(self):
        class BrokenTracePipeline:
            def run(self, incident, at=None):
                result = Pipeline().run(incident, at=at)
                result.proposal.evidence_ids = ["invented"]
                result.trace[-1].run_id = "another-run"
                return result
        data = evaluate(pipeline_factory=BrokenTracePipeline)
        self.assertEqual(data["metrics"]["valid_citation_ids"], 20)
        self.assertEqual(data["metrics"]["citation_ids_checked"], 30)
        self.assertEqual(data["metrics"]["valid_trace_run_ids"], 0)

    def test_missed_and_extra_review_denominators(self):
        rows = [EvaluationCase.model_validate(row) for row in self.data["rows"][:2]]
        for row in rows:
            actual = EvaluationDecision(assessment=row.actual.assessment, risk=row.actual.risk,
                                        human_review=not row.expected.human_review)
            row.actual = actual
            row.field_agreement = agreements(actual, row.expected)
            row.passed = all(row.field_agreement.values())
        metrics = aggregate_metrics(rows, 4, 4, [1, 2, 3, 4])
        self.assertEqual(metrics.expected_reviews, 1)
        self.assertEqual(metrics.system_required_reviews, 1)
        self.assertEqual(metrics.system_missed_reviews, 1)
        self.assertEqual(metrics.system_extra_reviews, 1)
        self.assertEqual(metrics.mean_duration_ms, 2.5)

    def test_pilot_and_trial_history_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            data = evaluate(store)
            reopened = Store(directory)
            restored = reopened.load_evaluation(data["evaluation_id"])
            self.assertEqual(restored.model_dump(mode="json"), data)
            self.assertEqual(len(reopened.recent()), 20)
            for row in data["rows"]:
                for trial in row["trials"]:
                    self.assertEqual(reopened.load(trial["run_id"]).run_id, trial["run_id"])

    def test_csv_and_json_retain_trial_links(self):
        result = PilotEvaluation.model_validate(json.loads(json.dumps(self.data)))
        rows = list(csv.DictReader(io.StringIO(evaluation_csv(result.model_dump(mode="json")))))
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["evaluation_id"] == result.evaluation_id for row in rows))
        self.assertTrue(all(len(row["trial_run_ids"].split("|")) == 2 for row in rows))
        self.assertIn("expected_review", rows[0])
        self.assertIn("baseline_review", rows[0])

    def test_invalid_repetition_counts_are_rejected(self):
        for repetitions in (1, 6, True, 2.5):
            with self.subTest(repetitions=repetitions), self.assertRaises(ValueError):
                evaluate(repetitions=repetitions)


if __name__ == "__main__":
    unittest.main()
