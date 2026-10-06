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

---

## Setup From Scratch (Recovery / Demo Backup Guide)

If the environment ever breaks right before a demo, rebuild it in this order. Each stage depends on the one before it, so don't skip ahead.

### 0. What's running where

```
Windows:         backend (FastAPI) + frontend (React/Vite) — in frontend/ and backend/
WSL2 / Kali:     Mininet (virtual network) + Suricata (IDS sensor)
Bridge file:     C:\ECOSHIELD\suricata_logs\eve.json  — written by Suricata (WSL),
                 read by backend/monitoring/traffic_monitor.py (Windows)
```

Three terminals are needed at demo time:

| Terminal | Runs | Must stay open |
|---|---|---|
| 1 | Mininet (`mininet>` CLI) | Yes — closing it tears down the virtual network |
| 2 | Suricata | Yes — this is the sensor |
| 3 (Windows) | Backend (`uvicorn` / `python main.py`) | Yes |
| + frontend | `npm run dev` (Vite) | Yes |

### 1. WSL2 + Kali (one-time)

```powershell
wsl --update
wsl --set-default-version 2
wsl --install -d kali-linux   # if not already installed
```

Reboot Windows after `wsl --update` if you hit `WSL_E_VM_MODE_INVALID_STATE` — the update needs a restart to take effect.

Check it worked:
```powershell
wsl -l -v        # kali-linux should show VERSION 2
```

### 2. Install tools inside Kali

```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch suricata nmap hping3 ethtool jq
```

### 3. Recreate the Mininet topology

```bash
mkdir -p ~/ecoshield-sim && cd ~/ecoshield-sim
cat > topology.py << 'EOF'
#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.log import setLogLevel

def run():
    net = Mininet(switch=OVSBridge, controller=None)
    h1 = net.addHost('h1', ip='10.0.0.1/24')  # attacker (you)
    h2 = net.addHost('h2', ip='10.0.0.2/24')  # target
    s1 = net.addSwitch('s1')
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.start()
    for intf in ('s1-eth1', 's1-eth2'):
        s1.cmd(f'ethtool -K {intf} tx off rx off gro off gso off tso off')
    for h in (h1, h2):
        h.cmd(f'ethtool -K {h.defaultIntf()} tx off rx off gro off gso off tso off')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
EOF
sudo service openvswitch-switch start
sudo python3 topology.py
```

Leave it at the `mininet>` prompt. Give the target something to answer on:
```
mininet> h2 python3 -m http.server 80 &
```

### 4. Recreate the Suricata rules

```bash
sudo mkdir -p /etc/suricata/rules
sudo tee /etc/suricata/rules/local.rules > /dev/null << 'EOF'
alert tcp any any -> $HOME_NET any (msg:"LOCAL SYN scan"; flags:S; detection_filter:track by_src, count 20, seconds 3; classtype:attempted-recon; sid:1000001; rev:1;)
alert tcp any any -> $HOME_NET 80 (msg:"LOCAL SYN flood"; flags:S; detection_filter:track by_src, count 100, seconds 2; classtype:attempted-dos; sid:1000002; rev:1;)
alert icmp any any -> $HOME_NET any (msg:"LOCAL ICMP flood"; itype:8; detection_filter:track by_src, count 50, seconds 2; classtype:attempted-dos; sid:1000003; rev:1;)
EOF
```

`HOME_NET` doesn't need editing — Suricata's default already covers `10.0.0.0/8`.

### 5. Start Suricata (second WSL terminal)

```bash
sudo mkdir -p /mnt/c/ECOSHIELD/suricata_logs
sudo suricata -c /etc/suricata/suricata.yaml -S /etc/suricata/rules/local.rules -i s1-eth2 -l /mnt/c/ECOSHIELD/suricata_logs
```

Wait for "engine started". If the interface doesn't exist, Mininet (step 3) isn't running yet — start that first.

### 6. Start the backend (Windows)

```powershell
cd backend
python main.py
```

Sanity check it's reading real alerts:
```powershell
Invoke-RestMethod http://localhost:8000/alerts
```

### 7. Start the frontend (Windows)

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`.

### 8. Fire a test attack

From the `mininet>` prompt (Terminal 1):
```
h1 nmap -sS -p 1-1000 10.0.0.2
```

Alerts should appear in the dashboard within ~5 seconds, and the risk score should rise.

### Quick troubleshooting

| Symptom | Likely cause |
|---|---|
| `ip link \| grep s1-eth` shows nothing | Mininet isn't running — redo step 3 |
| Suricata won't start / interface error | Same as above, or Suricata already running elsewhere — check with `ps aux \| grep suricata` |
| `/alerts` returns `total: 0` after attacking | Backend was started *before* the attack and missed it (it only reads new lines) — attack again now that it's running, or restart backend then attack |
| Dashboard shows no alert panel | Frontend is running an older `app.jsx` — redeploy the current one and hard refresh (Ctrl+Shift+R) |
| Risk score spikes but tier never changes | Normal for a short scan — hysteresis needs 3 consecutive high readings; run a longer scan or flood (see below) |
| High system memory / browser tab "snoozed" | Opera/Chrome auto-suspends tabs under memory pressure — click "Disable" on the banner, or cap WSL2 memory via `.wslconfig` |

---

## Attack Cheat Sheet (run from the `mininet>` CLI, against h2 = 10.0.0.2)

### Port scans (nmap)

```
h1 nmap -sS -p 1-1000 10.0.0.2          # quick SYN scan, first 1000 ports
h1 nmap -sS -p- --min-rate 2000 10.0.0.2   # full 65535-port scan, fast
h1 nmap -sS -T4 -p 1-1000 10.0.0.2      # faster timing template
h1 nmap -sV -p 80 10.0.0.2              # service/version detection on port 80
h1 nmap -A -p 1-1000 10.0.0.2           # aggressive: OS detection + version + scripts
```

### Floods (hping3) — always stop with Ctrl+C after a few seconds

```
h1 hping3 -S -p 80 --flood 10.0.0.2           # SYN flood on port 80
h1 hping3 -S -p 80 -i u1000 -c 500 10.0.0.2   # throttled SYN flood, 500 packets, 1ms apart
h1 hping3 --icmp --flood 10.0.0.2             # ICMP flood
h1 hping3 -2 -p 80 --flood 10.0.0.2           # UDP flood on port 80
```

### ICMP (ping) — self-limiting, no Ctrl+C needed

```
h1 ping -f -c 2000 10.0.0.2    # flood ping, 2000 packets
h1 ping -c 20 10.0.0.2         # normal ping, for a sanity check
```

### Combined pressure (to reach INTENSIVE tier)

Run a scan and a flood at the same time — scan in the main CLI, flood in a second window attached to h1:
```
mininet> xterm h1
```
In the new xterm window:
```
hping3 -S -p 80 --flood 10.0.0.2
```
Back in the `mininet>` prompt:
```
h1 nmap -sS -p- --min-rate 2000 10.0.0.2
```