"""
Traffic Monitor (SIMULATED)
----------------------------
This is a placeholder that generates plausible-looking traffic features
so the rest of the pipeline (risk engine -> hysteresis -> controller) can
be built, tested, and demoed BEFORE Mininet/Suricata are integrated.

Later: replace get_simulated_features() with a real function that reads
from Suricata's eve.json and computed traffic stats. Everything downstream
(main.py, scorer.py) only cares about receiving a TrafficFeatures object —
so this swap won't require changing any other file.
"""

import random
from risk_engine.scorer import TrafficFeatures

# Simple state machine so simulated traffic drifts (not just random noise
# every call) — makes the hysteresis behavior visible in a demo.
_state = {"phase": "quiet", "ticks_left": 15}


def _pick_next_phase():
    _state["phase"] = random.choice(["quiet", "quiet", "quiet", "suspicious", "attack"])
    _state["ticks_left"] = random.randint(8, 20)


def get_simulated_features() -> TrafficFeatures:
    if _state["ticks_left"] <= 0:
        _pick_next_phase()
    _state["ticks_left"] -= 1

    phase = _state["phase"]

    if phase == "quiet":
        return TrafficFeatures(
            packet_rate=random.uniform(0.05, 0.2),
            unique_connections=random.uniform(0.05, 0.2),
            ids_alert_count=random.randint(0, 1),
            ids_alert_severity=random.uniform(0.0, 0.1),
            failed_conn_ratio=random.uniform(0.0, 0.1),
        )
    elif phase == "suspicious":
        return TrafficFeatures(
            packet_rate=random.uniform(0.3, 0.6),
            unique_connections=random.uniform(0.3, 0.5),
            ids_alert_count=random.randint(2, 6),
            ids_alert_severity=random.uniform(0.3, 0.6),
            failed_conn_ratio=random.uniform(0.2, 0.4),
        )
    else:  # attack
        return TrafficFeatures(
            packet_rate=random.uniform(0.7, 1.0),
            unique_connections=random.uniform(0.6, 0.9),
            ids_alert_count=random.randint(8, 20),
            ids_alert_severity=random.uniform(0.7, 1.0),
            failed_conn_ratio=random.uniform(0.5, 0.9),
        )
