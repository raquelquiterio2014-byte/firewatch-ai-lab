import tempfile
import unittest
from datetime import timedelta

from firewatch.models import RunResult, SharedState
from firewatch.pipeline import Pipeline, workflow_mermaid
from firewatch.reference_pipeline import ReferencePipeline
from firewatch.scenarios import SCENARIOS, get_scenario, sample
from firewatch.storage import Store
from test_firewatch import ScriptedGateway


class V2GraphTests(unittest.TestCase):
    def test_catalogue_matches_v1_reference(self):
        for name in SCENARIOS:
            with self.subTest(name=name):
                incident = get_scenario(name)
                legacy = ReferencePipeline().run(incident)
                current = Pipeline().run(incident)
                self.assertEqual(current.assessment.model_dump(), legacy.assessment.model_dump())
                self.assertEqual(current.risk.model_dump(), legacy.risk.model_dump())
                self.assertEqual(current.safety.model_dump(), legacy.safety.model_dump())

    def test_complete_case_skips_information_branch(self):
        result = Pipeline().run(sample("Complete", smoke="no", flames="no", exposure="no"))
        nodes = [step.node for step in result.graph_steps]
        self.assertNotIn("information_request", nodes)
        self.assertNotIn("revision", nodes)
        self.assertEqual(nodes[-1], "human_gate")
        self.assertEqual(result.orchestrator, "langgraph")

    def test_unknown_case_executes_information_branch(self):
        result = Pipeline().run(sample("Unknown"))
        nodes = [step.node for step in result.graph_steps]
        self.assertEqual(nodes[2], "information_request")
        self.assertEqual(result.incident.flames, "unknown")
        self.assertEqual(result.evidence_quality.completeness, "INSUFFICIENT")

    def test_model_selected_route_is_executed(self):
        result = Pipeline(ScriptedGateway()).run(sample("Complete", smoke="no", flames="no", exposure="no"), use_llm=True)
        self.assertIn("information_request", [s.node for s in result.graph_steps])

    def test_revision_branch_is_bounded(self):
        result = Pipeline(ScriptedGateway(reject=True)).run(sample("Revision"), use_llm=True)
        nodes = [step.node for step in result.graph_steps]
        self.assertEqual(nodes.count("revision"), 1)
        self.assertEqual(nodes.count("decision"), 2)
        self.assertEqual(nodes.count("critic"), 2)
        self.assertEqual(nodes.count("safety_gate"), 1)
        self.assertTrue(result.safety.human_review_required)

    def test_streamed_snapshots_are_detached_and_persisted(self):
        observed = []
        def callback(step):
            observed.append((step.node, step.run_id))
            step.state["observation"]["flames"] = "invented"
        result = Pipeline().run(sample("Stream"), on_step=callback)
        self.assertEqual(len(observed), len(result.graph_steps))
        self.assertTrue(all(s.state["observation"]["flames"] == "unknown" for s in result.graph_steps))
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.save(result)
            self.assertEqual(store.load(result.run_id).graph_steps, result.graph_steps)

    def test_evidence_quality_is_descriptive_not_confidence(self):
        result = Pipeline().run(sample("Partial old", smoke="yes", stale=True, conflict=True))
        quality = result.evidence_quality
        self.assertEqual(quality.completeness, "PARTIAL")
        self.assertEqual(quality.known_indicator_fields, 1)
        self.assertTrue(quality.stale_ids)
        self.assertTrue(quality.flagged_conflicts)
        self.assertEqual(quality.provenance_counts, {"synthetic": 1})
        self.assertNotIn("confidence", quality.model_dump())
        self.assertTrue(result.safety.human_review_required)

    def test_v1_snapshot_still_loads(self):
        result = ReferencePipeline().run(sample("Legacy"))
        data = result.model_dump(mode="json")
        for key in ("orchestrator", "graph_steps", "evidence_quality"):
            data.pop(key)
        restored = RunResult.model_validate(data)
        self.assertEqual(restored.orchestrator, "python-v1")
        self.assertEqual(restored.graph_steps, [])
        self.assertIsNone(SharedState.from_run(restored).evidence_quality)

    def test_graph_topology_has_conditional_and_loop_edges(self):
        text = workflow_mermaid()
        self.assertIn("information_request", text)
        self.assertIn("revision", text)
        self.assertIn("safety_gate", text)


class V2InputTests(unittest.TestCase):
    def test_editing_form_invalidates_previous_results(self):
        from firewatch.gui import FireWatchApp
        class Var:
            def __init__(self): self.value = "OLD"
            def set(self, value): self.value = value
        class Canvas:
            def itemconfigure(self, *args, **kwargs): pass
        app = FireWatchApp.__new__(FireWatchApp)
        app.filling_form = False
        app.busy = False
        app.current = object()
        app.status = Var()
        app.card_vars = {key: Var() for key in ("Assessment", "Priority", "Human review", "Mode")}
        app.outputs = {"Workflow": None, "Evaluation": None}
        written = []
        app.set_output = lambda name, content: written.append(name)
        app.flow_boxes = {}
        app.flow_canvas = Canvas()
        app.input_changed()
        self.assertIsNone(app.current)
        self.assertEqual(app.card_vars["Assessment"].value, "NOT ANALYZED")
        self.assertEqual(app.card_vars["Mode"].value, "PENDING")
        self.assertEqual(written, ["Workflow"])


if __name__ == "__main__":
    unittest.main()
