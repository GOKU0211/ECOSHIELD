"""
Risk Scorer
-----------
Converts raw network features + IDS alert data into a single risk score (0-100).

Design choice: a transparent weighted sum instead of an ML model.
Why: it's explainable (you can point at a number and say exactly why),
it's fast, and it's a legitimate baseline that ML can later be compared against.
"""

from dataclasses import dataclass


@dataclass
class TrafficFeatures:
    """Raw signals collected during one monitoring interval."""
    packet_rate: float          # packets/sec, normalized 0-1 against a known baseline
    unique_connections: float   # unique src/dst pairs, normalized 0-1
    ids_alert_count: int        # number of Suricata alerts in this interval
    ids_alert_severity: float   # 0-1, average severity of alerts in this interval (0=low,1=critical)
    failed_conn_ratio: float    # ratio of failed/reset connections, 0-1


# Weights must sum to 1.0 — this is what makes the score interpretable as a percentage.
# These are starting values; tune them empirically once you have real traffic captures.
WEIGHTS = {
    "packet_rate": 0.15,
    "unique_connections": 0.15,
    "ids_alert_count": 0.25,
    "ids_alert_severity": 0.30,
    "failed_conn_ratio": 0.15,
}


def normalize_alert_count(count: int, cap: int = 10) -> float:
    """
    Alert count is unbounded (could be 0 or could be 500), but our weighted
    sum needs every input on a 0-1 scale. We cap it: anything at or above
    `cap` alerts in one interval is treated as maximally suspicious.
    """
    return min(count / cap, 1.0)


def compute_risk_score(features: TrafficFeatures) -> float:
    """
    Returns a risk score from 0 to 100.

    This is deliberately just a dot product of features and weights,
    scaled to 0-100. No hidden logic. If someone asks "why is the risk
    82?", you can show this exact calculation.
    """
    normalized_alerts = normalize_alert_count(features.ids_alert_count)

    weighted_sum = (
        WEIGHTS["packet_rate"] * features.packet_rate
        + WEIGHTS["unique_connections"] * features.unique_connections
        + WEIGHTS["ids_alert_count"] * normalized_alerts
        + WEIGHTS["ids_alert_severity"] * features.ids_alert_severity
        + WEIGHTS["failed_conn_ratio"] * features.failed_conn_ratio
    )

    score = weighted_sum * 100
    return round(min(max(score, 0.0), 100.0), 2)  # clamp to [0, 100]


if __name__ == "__main__":
    # Quick sanity check — run this file directly to see example scores.
    quiet_network = TrafficFeatures(
        packet_rate=0.1, unique_connections=0.1,
        ids_alert_count=0, ids_alert_severity=0.0, failed_conn_ratio=0.05,
    )
    under_attack = TrafficFeatures(
        packet_rate=0.9, unique_connections=0.8,
        ids_alert_count=15, ids_alert_severity=0.9, failed_conn_ratio=0.7,
    )

    print("Quiet network score:", compute_risk_score(quiet_network))
    print("Under attack score:", compute_risk_score(under_attack))
