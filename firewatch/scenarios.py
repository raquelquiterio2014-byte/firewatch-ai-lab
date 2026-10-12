from datetime import timedelta

from .models import Evidence, Incident, now


def sample(name, *, smoke="unknown", flames="unknown", exposure="unknown", stale=False,
           conflict=False, **context):
    observed = now() - timedelta(hours=12 if stale else 0)
    description = f"Synthetic scenario: {name}. No real incident or measured sensor input."
    record = Evidence(source="FireWatch synthetic catalogue", observed_at=observed,
                      content=description, conflicts=conflict)
    return Incident(location="Simulation area — not a real location", smoke=smoke,
                    flames=flames, exposure=exposure, description=description,
                    evidence=[record], **context)


SCENARIOS = {
    "01 — No reported indicators": dict(smoke="no", flames="no", exposure="no"),
    "02 — Smoke, unknown exposure": dict(smoke="yes", flames="no", exposure="unknown"),
    "03 — Flames near people": dict(smoke="yes", flames="yes", exposure="yes"),
    "04 — Dry vegetation, unknown indicators": dict(vegetation="dry", humidity_pct=20),
    "05 — Conflicting reports": dict(smoke="yes", flames="no", exposure="no", conflict=True),
    "06 — Old observation": dict(smoke="no", flames="no", exposure="no", stale=True),
    "07 — Smoke, no reported exposure": dict(smoke="yes", flames="no", exposure="no"),
    "08 — Flames, unknown exposure": dict(smoke="unknown", flames="yes", exposure="unknown"),
    "09 — Dry weather, no indicators": dict(smoke="no", flames="no", exposure="no", vegetation="dry", humidity_pct=10),
    "10 — Partial observation": dict(smoke="no", flames="unknown", exposure="no"),
}


def get_scenario(name):
    return sample(name, **SCENARIOS[name])
