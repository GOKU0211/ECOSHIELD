"""
Resource Monitor
-----------------
Measures the computational cost of running security operations at the
CURRENT tier. This is the data that lets us answer the research question:
"does adapting intensity actually save resources?"

Important honesty note (put this in your report too): we do NOT have a
hardware power meter. "Estimated energy" here is a proxy computed from
CPU utilization and elapsed time, not a real wattage reading. Never present
it as measured energy in your viva — always say "estimated".
"""

import time
import psutil
from dataclasses import dataclass, asdict


@dataclass
class ResourceSnapshot:
    timestamp: float
    cpu_percent: float          # % CPU used system-wide at sampling instant
    memory_percent: float       # % RAM used system-wide
    process_cpu_percent: float  # % CPU used by THIS process (the security engine)
    process_memory_mb: float    # RAM used by this process, in MB
    estimated_energy_units: float  # proxy metric, see note below


# A rough proxy: energy ~ CPU_load x time. This is NOT calibrated to real
# watts. It's a comparative metric — useful for saying "Config B used 40%
# less estimated energy than Config A", not for absolute claims.
ENERGY_PROXY_COEFFICIENT = 1.0


class ResourceMonitor:
    def __init__(self):
        self._process = psutil.Process()
        # First call to cpu_percent() always returns 0.0 (needs a baseline) —
        # call it once here so real readings later are meaningful.
        self._process.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None)

    def sample(self, interval_seconds: float = 0.0) -> ResourceSnapshot:
        """
        Takes one resource reading. If interval_seconds > 0, cpu_percent()
        will block and measure CPU usage averaged over that window (more
        accurate); if 0, it returns usage since the last call (non-blocking,
        better for a fast polling loop).
        """
        system_cpu = psutil.cpu_percent(interval=interval_seconds if interval_seconds > 0 else None)
        system_mem = psutil.virtual_memory().percent

        proc_cpu = self._process.cpu_percent(interval=None)
        proc_mem_mb = self._process.memory_info().rss / (1024 * 1024)

        # Simple proxy: process CPU% x coefficient. Multiply by tier-specific
        # workload later if you want to weight Intensive mode's extra work.
        estimated_energy = proc_cpu * ENERGY_PROXY_COEFFICIENT

        return ResourceSnapshot(
            timestamp=time.time(),
            cpu_percent=system_cpu,
            memory_percent=system_mem,
            process_cpu_percent=proc_cpu,
            process_memory_mb=round(proc_mem_mb, 2),
            estimated_energy_units=round(estimated_energy, 4),
        )

    def sample_dict(self, interval_seconds: float = 0.0) -> dict:
        return asdict(self.sample(interval_seconds))


if __name__ == "__main__":
    rm = ResourceMonitor()
    print("Sampling resource usage over 1 second...")
    snap = rm.sample(interval_seconds=1.0)
    print(snap)
