"""Windows CI widget/interaction check; not manual layout acceptance."""
import tempfile
import tkinter as tk
from datetime import datetime, timezone

from firewatch.gui import FireWatchApp
from firewatch.pipeline import Pipeline
from firewatch.research import run_shadow


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = tk.Tk()
        root.withdraw()
        try:
            app = FireWatchApp(root, directory)
            assert len(app.tabs.tabs()) == 11
            app.context_fields["slope_deg"].set("15")
            incident = app.collect()
            assert incident.context.slope_deg == 15
            assert incident.context_evidence_ids == [incident.evidence[0].id]
            result = Pipeline().run(incident)
            app.store.save(result)
            app.display(result)
            assert app.current.run_id == result.run_id
            app.human_fields["reviewer"].set("CI fixture — not a human evaluation")
            app.human_fields["assessment"].set("NO_INDICATION")
            app.human_fields["risk"].set("LOW")
            app.human_fields["human_review"].set("OPTIONAL")
            app.human_rationale.set("Automated widget fixture only")
            app.save_human_assessment()
            assert len(app.store.human_assessments(result.run_id)) == 1
            app.load_shadow_demo()
            shadow = run_shadow(app.shadow_dataset, datetime(2026, 10, 14, 12, tzinfo=timezone.utc), store=app.store)
            app.show_shadow(shadow)
            app.refresh_history()
            assert app.shadow_history_map
            app.context_fields["slope_deg"].set("20")
            assert app.current is None
            assert app.card_vars["Mode"].get() == "PENDING"
            root.update_idletasks()
            print("V5 GUI construction and interactions: OK (automated fixture, layout acceptance pending)")
        finally:
            root.destroy()


if __name__ == "__main__":
    main()
