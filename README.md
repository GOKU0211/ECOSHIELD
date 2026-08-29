# EcoShield

**Risk-adaptive network security prototype** that dynamically scales security monitoring intensity based on real-time network risk — instead of running always-on, maximum-intensity security controls regardless of actual threat level.

## Problem

Always-on, high-intensity network security consumes significant CPU, memory, processing time, and energy — even when the network is behaving normally. EcoShield asks:

> Can we reduce computational and energy overhead by dynamically adapting security intensity to network risk, without significantly hurting detection and response performance?

## How It Works

EcoShield runs a continuous closed-loop cycle:

```
Traffic → Monitoring → Feature Extraction → Risk Engine
    → Risk Score / Level → Adaptive Controller
    → [Baseline | Elevated | Intensive]
    → Resource Monitor (CPU, RAM, time, est. energy/CO₂)
    → Dashboard → Feedback → (loop)
```

- **Risk Engine**: computes a transparent, weighted risk score (0–100) from traffic features and IDS alerts.
- **Adaptive Controller**: maps the risk score to one of three security tiers — Baseline, Elevated, or Intensive — each with a different depth of monitoring and inspection.
- **Hysteresis / Persistence**: tier switches require sustained risk levels (not a single spike), preventing rapid flickering between modes.
- **Resource Monitor**: tracks the computational cost (CPU, memory, processing time) and estimated energy/CO₂ of running security operations at the current tier.
- **Dashboard**: live view of current risk, current mode, alerts, traffic stats, and historical resource usage.

This makes EcoShield a **closed-loop adaptive security system**, not a traditional always-on IDS.

## Research Question

Does risk-adaptive security intensity reduce computational and estimated energy overhead compared to an always-on, high-intensity configuration — while maintaining acceptable detection and response performance?

## Evaluation

Two configurations are compared under identical simulated threat conditions (low / medium / high):

| Configuration | Behavior |
|---|---|
| **A — Always-On** | Security runs at maximum intensity at all times |
| **B — EcoShield** | Security intensity adapts to current risk level |

**Metrics measured:**
- Detection Rate
- False Positive Rate
- Response Time
- CPU Utilization
- Memory Usage
- Processing Time
- Estimated Energy / CO₂

## Tech Stack

| Layer | Tool |
|---|---|
| Network simulation | Mininet |
| Traffic / attack generation | Scapy |
| IDS | Suricata |
| Backend | Python + FastAPI |
| Risk engine | Python (weighted scoring) |
| Resource monitoring | psutil |
| Database | SQLite |
| Frontend | React + Recharts |
| Traffic analysis | Wireshark |
| Containerization | Docker (optional) |

## Project Structure

```
ecoshield/
├── backend/
│   ├── main.py
│   ├── risk_engine/          # scoring + hysteresis logic
│   ├── controller/           # adaptive tier switching
│   ├── monitoring/           # traffic, feature extraction, resource monitor
│   ├── ids/                  # Suricata alert parsing
│   ├── db/                   # SQLite models
│   └── api/                  # REST endpoints
├── network_sim/              # Mininet topology + Scapy attack generation
├── frontend/                 # React dashboard
├── docker/                   # docker-compose + Suricata config
├── experiments/              # Config A vs Config B evaluation scripts
└── docs/
```

## Scope

EcoShield is a **controlled prototype and experimental evaluation**, built for a 3-month academic project. It is explicitly **not**: an enterprise SOC, a full SIEM, a commercial firewall, an autonomous AI cybersecurity platform, or a custom deep-learning IDS built from scratch.

## Related Work

EcoShield differentiates itself from prior work in two key ways:
- Unlike adaptive deep-learning IDS approaches (which adapt the *detection model*), EcoShield adapts the *intensity of security controls* themselves.
- Unlike federated-learning approaches for energy-efficient intrusion detection (which optimize *learning/communication*), EcoShield optimizes *how much security processing runs at a given risk level*.

## Status

🚧 In development — academic semester project.
