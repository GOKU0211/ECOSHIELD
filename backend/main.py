"""
EcoShield Backend — main entrypoint
-------------------------------------
Closed loop: traffic features -> risk score -> hysteresis -> active tier
    -> controller config -> resource monitor reading -> stored in SQLite
    -> exposed via API for the dashboard.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
from risk_engine.scorer import compute_risk_score
from risk_engine.hysteresis import HysteresisController
from controller.adaptive_controller import AdaptiveController
from monitoring.resource_monitor import ResourceMonitor
from monitoring.traffic_monitor import get_real_features, get_recent_alerts, get_alert_summary
from db.db import init_db
from db.models import insert_reading, insert_tier_event, get_recent_readings, get_recent_tier_events

app = FastAPI(title="EcoShield Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



hysteresis = HysteresisController(persistence=3)
controller = AdaptiveController()
resource_monitor = ResourceMonitor()

latest_state = {
    "risk_score": 0.0,
    "active_tier": "BASELINE",
    "tier_config": {},
    "resource_snapshot": {},
    "updated_at": None,
}

_previous_tier = "BASELINE"  # tracked here so we know when to log a tier_event

async def monitoring_loop():
    global _previous_tier

    while True:
        features = get_real_features()
        score = compute_risk_score(features)
        active_tier = hysteresis.update(score)
        tier_cfg = controller.apply(active_tier)
        snapshot = resource_monitor.sample()
        now = time.time()

        # Persist this tick to SQLite — this is the data your dashboard's
        # history charts and your experiment analysis will both read from.
        insert_reading(
            risk_score=score,
            active_tier=active_tier.value,
            cpu_percent=snapshot.cpu_percent,
            memory_percent=snapshot.memory_percent,
            process_cpu_percent=snapshot.process_cpu_percent,
            process_memory_mb=snapshot.process_memory_mb,
            estimated_energy_units=snapshot.estimated_energy_units,
            timestamp=now,
        )

        # Only log a tier_event when the tier actually changed —
        # this table answers "when and how often did the system escalate?"
        if active_tier.value != _previous_tier:
            insert_tier_event(from_tier=_previous_tier, to_tier=active_tier.value, timestamp=now)
            _previous_tier = active_tier.value

        latest_state.update({
            "risk_score": score,
            "active_tier": active_tier.value,
            "tier_config": {
                "poll_interval_seconds": tier_cfg.poll_interval_seconds,
                "inspection_depth": tier_cfg.inspection_depth,
                "logging_verbosity": tier_cfg.logging_verbosity,
                "suricata_ruleset": tier_cfg.suricata_ruleset,
            },
            "resource_snapshot": {
                "cpu_percent": snapshot.cpu_percent,
                "memory_percent": snapshot.memory_percent,
                "process_cpu_percent": snapshot.process_cpu_percent,
                "process_memory_mb": snapshot.process_memory_mb,
                "estimated_energy_units": snapshot.estimated_energy_units,
            },
            "updated_at": now,
        })

        await asyncio.sleep(tier_cfg.poll_interval_seconds)


@app.on_event("startup")
async def start_background_loop():
    init_db()  # creates tables if they don't exist yet — safe to call every startup
    asyncio.create_task(monitoring_loop())


# --- API endpoints ---------------------------------------------------------

@app.get("/risk")
def get_risk():
    return {
        "risk_score": latest_state["risk_score"],
        "active_tier": latest_state["active_tier"],
        "updated_at": latest_state["updated_at"],
    }


@app.get("/mode")
def get_mode():
    return {
        "active_tier": latest_state["active_tier"],
        "tier_config": latest_state["tier_config"],
    }


@app.get("/metrics")
def get_metrics():
    return latest_state["resource_snapshot"]


@app.get("/status")
def get_status():
    return latest_state


@app.get("/alerts")
def get_alerts(limit: int = 50):
    """Real Suricata alerts (newest first) + counts, for the dashboard."""
    return {"alerts": get_recent_alerts(limit=limit), "summary": get_alert_summary()}


@app.get("/history")
def get_history(limit: int = 100):
    """
    Historical readings for dashboard charts. Returns oldest-first so a
    line chart can plot them left-to-right in chronological order.
    """
    return {
        "readings": get_recent_readings(limit=limit),
        "tier_events": get_recent_tier_events(limit=50),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)