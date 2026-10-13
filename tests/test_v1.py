import unittest

from firewatch.models import HumanReview, SharedState
from firewatch.pipeline import Pipeline
from firewatch.presentation import agent_summary
from firewatch.scenarios import sample


class V1Tests(unittest.TestCase):
    def test_shared_state_preserves_unknowns_and_safety(self):
        result = Pipeline().run(sample("V1 unknown"))
        state = SharedState.from_run(result)
        self.assertEqual(state.incident.flames, "unknown")
        self.assertIsNone(state.incident.humidity_pct)
        self.assertTrue(state.safety_gate.human_review_required)
        state.incident.location = "Edited view"
        self.assertNotEqual(state.incident.location, result.incident.location)

    def test_human_approval_does_not_erase_safety(self):
        result = Pipeline().run(sample("V1 flames", flames="yes", exposure="yes"))
        review = HumanReview(run_id=result.run_id, reviewer="Test", comment="Reviewed", decision="APPROVED")
        state = SharedState.from_run(result, [review])
        self.assertEqual(state.human_reviews[0].decision, "APPROVED")
        self.assertTrue(state.safety_gate.human_review_required)

    def test_readable_summary_uses_actual_result(self):
        result = Pipeline().run(sample("V1 summary", flames="yes", exposure="yes"))
        text = agent_summary(result)
        self.assertIn(result.run_id, text)
        self.assertIn("FireAssessment [deterministic]", text)
        self.assertIn("STRONG_INDICATION", text)
        self.assertIn("Human review: REQUIRED", text)


if __name__ == "__main__":
    unittest.main()
