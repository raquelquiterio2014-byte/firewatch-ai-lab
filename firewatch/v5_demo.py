"""Fixed synthetic fixture, not a researched real incident."""
from .models import ShadowDataset


def shadow_demo():
    return ShadowDataset.model_validate({
        "dataset_id": "v5-synthetic-cutoff-demo",
        "location": "Simulation area — no real incident",
        "records": [
            {"evidence": {"id": "demo-early", "source": "Synthetic early observation",
                          "observed_at": "2026-10-14T11:00:00Z", "content": "Synthetic: no smoke or flames reported at 11:00."},
             "available_at": "2026-10-14T11:05:00Z",
             "values": {"smoke": "no", "flames": "no", "exposure": "no"}},
            {"evidence": {"id": "demo-context", "source": "Synthetic context record",
                          "observed_at": "2026-10-14T11:15:00Z", "content": "Synthetic environmental context only."},
             "available_at": "2026-10-14T11:20:00Z",
             "values": {"humidity_pct": 20, "wind_kmh": 25,
                        "context": {"fuel_type": "grass", "slope_deg": 15, "gust_kmh": 40}}},
            {"evidence": {"id": "demo-late", "source": "Synthetic later report",
                          "observed_at": "2026-10-14T11:30:00Z", "content": "Synthetic flames reported, but this report arrived only after the cutoff."},
             "available_at": "2026-10-14T13:00:00Z",
             "values": {"flames": "yes", "exposure": "yes", "context": {"people_present": "yes"}}},
            {"evidence": {"id": "demo-unknown-availability", "source": "Synthetic undated availability",
                          "observed_at": "2026-10-14T11:45:00Z", "content": "Synthetic smoke; availability time is unknown."},
             "values": {"smoke": "yes"}},
        ],
    })
