"""
Traffic Monitor (REAL — reads Suricata's eve.json)
---------------------------------------------------
Tails eve.json incrementally and converts the last WINDOW_S seconds of
events into the TrafficFeatures object scorer.py expects.

Event types used:
  alert -> ids_alert_count, ids_alert_severity, unique_connections
  stats -> packet_rate  (delta of decoder.pkts between stats events)
  flow  -> failed_conn_ratio (flows with no reply), unique_connections

Set EVE_PATH to override the default location.
"""

import json
import os
import time
from collections import Counter, deque
from datetime import datetime

from risk_engine.scorer import TrafficFeatures

EVE_PATH = os.environ.get("EVE_PATH", r"C:\ECOSHIELD\suricata_logs\eve.json")

WINDOW_S = 30          # sliding window used for features
PPS_CAP = 2000.0       # packets/sec treated as "maximum" (normalizes to 1.0)
CONN_CAP = 50.0        # unique src/dst/port tuples treated as maximum
STATS_STALE_S = 20     # ignore a packet-rate reading older than this

# Suricata severity: 1 = high, 2 = medium, 3 = low  ->  0-1 scale
_SEV = {1: 1.0, 2: 0.85, 3: 0.4}

_pos = None            # file offset; None until first read (starts at end of file)
_buf = b""
_alerts = deque(maxlen=500)   # parsed alerts kept for the dashboard
_flows = deque(maxlen=2000)   # (ingest_ts, conn_key, answered)
_last_pkts = None             # (cumulative pkts, ingest_ts)
_pps = (0.0, 0.0)             # (packets/sec, ingest_ts)
_next_id = 1


def _parse_ts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    except Exception:
        return time.time()


def _read_new_lines():
    """Return complete new lines appended to eve.json since the last call."""
    global _pos, _buf
    try:
        size = os.path.getsize(EVE_PATH)
    except OSError:
        return []
    if _pos is None:        # first call: skip history, only watch new events
        _pos = size
        return []
    if size < _pos:         # file truncated/rotated
        _pos, _buf = 0, b""
    if size == _pos:
        return []
    with open(EVE_PATH, "rb") as f:
        f.seek(_pos)
        data = f.read(size - _pos)
        _pos = f.tell()
    _buf += data
    *lines, _buf = _buf.split(b"\n")
    return lines


def _ingest():
    global _next_id, _last_pkts, _pps
    now = time.time()
    for raw in _read_new_lines():
        try:
            ev = json.loads(raw)
        except Exception:
            continue
        et = ev.get("event_type")

        if et == "alert":
            a = ev.get("alert", {})
            _alerts.append({
                "id": _next_id,
                "timestamp": _parse_ts(ev.get("timestamp", "")),
                "ingested": now,
                "src_ip": ev.get("src_ip"),
                "dest_ip": ev.get("dest_ip"),
                "dest_port": ev.get("dest_port"),
                "proto": ev.get("proto"),
                "signature": a.get("signature", "unknown"),
                "severity": a.get("severity", 3),
            })
            _next_id += 1

        elif et == "flow":
            fl = ev.get("flow", {})
            key = (ev.get("src_ip"), ev.get("dest_ip"), ev.get("dest_port"))
            _flows.append((now, key, fl.get("pkts_toclient", 0) > 0))

        elif et == "stats":
            pkts = ev.get("stats", {}).get("decoder", {}).get("pkts")
            if pkts is not None:
                if _last_pkts is not None and now > _last_pkts[1]:
                    rate = max(0, pkts - _last_pkts[0]) / (now - _last_pkts[1])
                    _pps = (rate, now)
                _last_pkts = (pkts, now)


def get_real_features() -> TrafficFeatures:
    _ingest()
    now = time.time()
    cutoff = now - WINDOW_S

    recent = [a for a in _alerts if a["ingested"] >= cutoff]
    flows = [f for f in _flows if f[0] >= cutoff]

    count = len(recent)
    severity = (sum(_SEV.get(a["severity"], 0.33) for a in recent) / count) if count else 0.0

    conns = {(a["src_ip"], a["dest_ip"], a["dest_port"]) for a in recent}
    conns |= {f[1] for f in flows}
    unique_conn = min(len(conns) / CONN_CAP, 1.0)

    failed = (sum(1 for f in flows if not f[2]) / len(flows)) if flows else 0.0

    pps, pps_ts = _pps
    packet_rate = min(pps / PPS_CAP, 1.0) if now - pps_ts <= STATS_STALE_S else 0.0

    return TrafficFeatures(
        packet_rate=packet_rate,
        unique_connections=unique_conn,
        ids_alert_count=count,
        ids_alert_severity=severity,
        failed_conn_ratio=failed,
    )


def get_recent_alerts(limit: int = 50):
    """Newest first, in the shape the dashboard needs."""
    out = []
    for a in list(_alerts)[-limit:][::-1]:
        out.append({k: v for k, v in a.items() if k != "ingested"})
    return out


def get_alert_summary():
    by_sig = Counter(a["signature"] for a in _alerts)
    by_src = Counter(a["src_ip"] for a in _alerts)
    return {
        "total": len(_alerts),
        "by_signature": dict(by_sig),
        "top_sources": by_src.most_common(5),
    }