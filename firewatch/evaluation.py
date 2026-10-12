"""Labels are fixed project expectations, not real-world ground truth."""
from .models import Incident
from .pipeline import Pipeline
from .scenarios import get_scenario


LABELS = [
    ("01 — No reported indicators", "NO_INDICATION", "LOW", False),
    ("02 — Smoke, unknown exposure", "POSSIBLE_FIRE", "UNDETERMINED", True),
    ("03 — Flames near people", "STRONG_INDICATION", "HIGH", True),
    ("04 — Dry vegetation, unknown indicators", "INSUFFICIENT_EVIDENCE", "UNDETERMINED", True),
    ("05 — Conflicting reports", "POSSIBLE_FIRE", "MEDIUM", True),
    ("06 — Old observation", "NO_INDICATION", "LOW", True),
    ("07 — Smoke, no reported exposure", "POSSIBLE_FIRE", "MEDIUM", True),
    ("08 — Flames, unknown exposure", "STRONG_INDICATION", "UNDETERMINED", True),
    ("09 — Dry weather, no indicators", "NO_INDICATION", "LOW", False),
    ("10 — Partial observation", "INSUFFICIENT_EVIDENCE", "UNDETERMINED", True),
]


def evaluate(store=None):
    rows = []
    for name, status, risk, review in LABELS:
        result = Pipeline().run(get_scenario(name))
        if store:
            store.save(result)
        actual = {"assessment": result.assessment.status, "risk": result.risk.level,
                  "human_review": result.safety.human_review_required}
        expected = {"assessment": status, "risk": risk, "human_review": review}
        fields = {key: actual[key] == value for key, value in expected.items()}
        rows.append({"scenario": name, "expected": expected, "actual": actual,
                     "field_agreement": fields, "passed": all(fields.values()),
                     "run_id": result.run_id, "duration_ms": result.duration_ms})
    return {"mode": "deterministic", "synthetic": True, "total": len(rows),
            "passed": sum(row["passed"] for row in rows), "rows": rows,
            "limitation": "Agreement with educational rules only; no real-world fire accuracy claim."}
