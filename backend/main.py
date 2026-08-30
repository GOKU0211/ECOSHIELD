"""
EcoShield Backend — main entrypoint
-------------------------------------
This wires together the full closed loop described in the architecture:

    traffic features -> risk score -> hysteresis -> active tier
        -> controller config -> resource monitor reading -> stored + exposed via API

For now, traffic features are SIMULATED (see monitoring/traffic_monitor.py).
Swap that module out once Suricata + Mininet are integrated — nothing else
in this file needs to change, because it only depends on TrafficFeatures
going in and a risk score coming out.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time

from risk_engine.scorer import compute_risk_score
from risk_engine.hysteresis import HysteresisController
from controller.adaptive_controller import AdaptiveController
from monitoring.resource_monitor import ResourceMonitor
from monitoring.traffic_monitor import get_simulated_features

app = FastAPI(title="EcoShield Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Shared state ---------------------------------------------------------
# Kept simple (in-memory) for the prototype. Swap for the SQLite layer
# (db/models.py) once you want persistence across restarts / historical charts.
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

POLL_INTERVAL_DEFAULT = 2.0  # seconds; the loop's own cadence


async def monitoring_loop():
    """
    The actual closed loop, running forever in the background.
    Each iteration: get features -> score risk -> update tier -> apply
    controller config -> measure resources -> store latest_state.
    """
    while True:
        features = get_simulated_features()
        score = compute_risk_score(features)
        active_tier = hysteresis.update(score)
        tier_cfg = controller.apply(active_tier)
        snapshot = resource_monitor.sample()

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
            "updated_at": time.time(),
        })

        # The tier's own poll_interval controls how "intensively" we're
        # sampling — this is where tier actually changes system load.
        await asyncio.sleep(tier_cfg.poll_interval_seconds)


@app.on_event("startup")
async def start_background_loop():
    asyncio.create_task(monitoring_loop())


# --- API endpoints ---------------------------------------------------------

@app.get("/risk")
def get_risk():
    """Current risk score and active security tier."""
    return {
        "risk_score": latest_state["risk_score"],
        "active_tier": latest_state["active_tier"],
        "updated_at": latest_state["updated_at"],
    }


@app.get("/mode")
def get_mode():
    """Current tier's concrete configuration (what the system is actually doing)."""
    return {
        "active_tier": latest_state["active_tier"],
        "tier_config": latest_state["tier_config"],
    }


@app.get("/metrics")
def get_metrics():
    """Latest resource usage snapshot."""
    return latest_state["resource_snapshot"]


@app.get("/status")
def get_status():
    """Everything at once — convenient for the dashboard's main poll."""
    return latest_state


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
