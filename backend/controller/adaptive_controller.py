"""
Adaptive Controller
--------------------
Takes the ACTIVE tier from the hysteresis controller and turns it into
concrete configuration: how often to poll, how deep to inspect, how much
to log. This is the piece that actually changes system behavior — without
it, "tiers" would just be labels with no effect.

For the prototype, these are simple, explainable knobs. You can wire
`inspection_depth` to a real Suricata ruleset selection later
(e.g. a lightweight ruleset for BASELINE, full ruleset for INTENSIVE).
"""

from dataclasses import dataclass
from risk_engine.hysteresis import SecurityTier


@dataclass
class TierConfig:
    tier: SecurityTier
    poll_interval_seconds: float   # how often we sample traffic/features
    inspection_depth: str          # "shallow" | "standard" | "deep"
    logging_verbosity: str         # "minimal" | "normal" | "verbose"
    suricata_ruleset: str          # which ruleset profile to load


TIER_CONFIGS = {
    SecurityTier.BASELINE: TierConfig(
        tier=SecurityTier.BASELINE,
        poll_interval_seconds=5.0,
        inspection_depth="shallow",
        logging_verbosity="minimal",
        suricata_ruleset="lightweight",
    ),
    SecurityTier.ELEVATED: TierConfig(
        tier=SecurityTier.ELEVATED,
        poll_interval_seconds=2.0,
        inspection_depth="standard",
        logging_verbosity="normal",
        suricata_ruleset="standard",
    ),
    SecurityTier.INTENSIVE: TierConfig(
        tier=SecurityTier.INTENSIVE,
        poll_interval_seconds=0.5,
        inspection_depth="deep",
        logging_verbosity="verbose",
        suricata_ruleset="full",
    ),
}


class AdaptiveController:
    """
    Thin wrapper that exposes the current tier's config and reports
    whenever a tier switch happens (useful for logging/dashboard events).
    """

    def __init__(self):
        self._current_tier = SecurityTier.BASELINE

    def apply(self, active_tier: SecurityTier) -> TierConfig:
        if active_tier != self._current_tier:
            print(f"[controller] tier switch: {self._current_tier.value} -> {active_tier.value}")
            self._current_tier = active_tier
        return TIER_CONFIGS[active_tier]


if __name__ == "__main__":
    ctrl = AdaptiveController()
    for tier in [SecurityTier.BASELINE, SecurityTier.BASELINE, SecurityTier.INTENSIVE, SecurityTier.ELEVATED]:
        cfg = ctrl.apply(tier)
        print(f"active={tier.value}: poll_every={cfg.poll_interval_seconds}s, "
              f"depth={cfg.inspection_depth}, ruleset={cfg.suricata_ruleset}")
