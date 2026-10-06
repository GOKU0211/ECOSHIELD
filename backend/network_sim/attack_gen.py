"""
Attack Generator
----------------
Generates test traffic patterns against YOUR OWN localhost backend so you can
watch risk_score / active_tier react in the dashboard. Everything here is
rate-limited and hardcoded to loopback — there is no parameter that lets a
caller point this at a real external host.

Three patterns, matched to what scorer.py actually weighs:
  - dos:        high packet_rate / unique_connections (volume)
  - port_scan:  high unique_connections, elevated failed_conn_ratio
  - intrusion:  trips Suricata-style alerts (ids_alert_count/severity) by
                hitting suspicious paths with suspicious payloads

Run via the /attack/start and /attack/stop routes in main.py, which call
launch()/stop() below.
"""

import socket
import threading
import time
import uuid
from urllib.request import Request, urlopen

from .topology import TARGET_HOST, TARGET_PORT, SCAN_PORT_RANGE


def require_local_target(host: str) -> None:
    """Hard safety rail: refuse to run against anything that isn't loopback."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(
            f"attack_gen will only target loopback addresses, got {host!r}. "
            "This tool is for testing your own machine only."
        )


class _RunningAttack:
    def __init__(self, attack_id, attack_type):
        self.attack_id = attack_id
        self.attack_type = attack_type
        self.stop_event = threading.Event()
        self.thread = None


class AttackGenerator:
    """Tracks running attack threads so /attack/stop can cancel them early."""

    def __init__(self):
        self._running: dict[str, _RunningAttack] = {}
        self._lock = threading.Lock()

    def launch(self, attack_type: str, duration_s: int = 20) -> str:
        require_local_target(TARGET_HOST)
        if attack_type not in ("dos", "port_scan", "intrusion"):
            raise ValueError(f"unknown attack type: {attack_type!r}")

        attack_id = uuid.uuid4().hex[:8]
        runner = _RunningAttack(attack_id, attack_type)
        target_fn = {
            "dos": self._run_dos,
            "port_scan": self._run_port_scan,
            "intrusion": self._run_intrusion,
        }[attack_type]

        runner.thread = threading.Thread(
            target=target_fn, args=(runner.stop_event, duration_s), daemon=True
        )
        with self._lock:
            self._running[attack_id] = runner
        runner.thread.start()
        return attack_id

    def stop(self, attack_id: str) -> None:
        with self._lock:
            runner = self._running.pop(attack_id, None)
        if runner:
            runner.stop_event.set()

    # --- patterns ------------------------------------------------------

    def _run_dos(self, stop_event, duration_s):
        """
        Rapid-fire GET requests at the backend's own root/health endpoint.
        This is a load generator, not an exploit — it just produces enough
        packet_rate/unique_connections for scorer.py to notice.
        """
        url = f"http://{TARGET_HOST}:{TARGET_PORT}/status"
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline and not stop_event.is_set():
            try:
                urlopen(Request(url, method="GET"), timeout=0.5).read()
            except Exception:
                pass  # connection errors are expected under load; keep going
            time.sleep(0.01)  # ~100 req/s cap — tune via this sleep, not by removing it

    def _run_port_scan(self, stop_event, duration_s):
        """Sequential TCP connect scan across SCAN_PORT_RANGE on TARGET_HOST."""
        deadline = time.monotonic() + duration_s
        for port in SCAN_PORT_RANGE:
            if time.monotonic() >= deadline or stop_event.is_set():
                break
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.05)
            try:
                s.connect((TARGET_HOST, port))
            except Exception:
                pass
            finally:
                s.close()

    def _run_intrusion(self, stop_event, duration_s):
        """
        Hits a handful of commonly-probed paths with suspicious-looking
        query strings. The point is to be the kind of traffic Suricata/
        traffic_monitor.py is meant to flag, not to actually exploit anything.
        """
        suspicious_paths = [
            "/admin",
            "/.env",
            "/wp-login.php",
            "/status?id=1' OR '1'='1",
            "/../../etc/passwd",
            "/status?q=<script>alert(1)</script>",
        ]
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline and not stop_event.is_set():
            for path in suspicious_paths:
                if time.monotonic() >= deadline or stop_event.is_set():
                    break
                url = f"http://{TARGET_HOST}:{TARGET_PORT}{path}"
                try:
                    urlopen(Request(url, method="GET"), timeout=0.5).read()
                except Exception:
                    pass
                time.sleep(0.2)


# Singleton used by main.py's routes.
attack_gen = AttackGenerator()