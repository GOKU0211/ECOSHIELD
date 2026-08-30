"""
Hysteresis / Persistence Logic
-------------------------------
Problem: a raw risk score fluctuates. If we switch security tier the instant
the score crosses a threshold, the system will flap:
    Baseline -> Elevated -> Baseline -> Elevated ...
every few seconds, which is neither realistic nor useful to evaluate.

Fix: require the score to stay in a new band for a minimum number of
consecutive readings ("persistence count") before we actually commit
to switching tiers. This is a standard control-systems technique.
"""

from collections import deque
from enum import Enum


class SecurityTier(str, Enum):
    BASELINE = "BASELINE"
    ELEVATED = "ELEVATED"
    INTENSIVE = "INTENSIVE"


# Score -> tier band mapping. Tune these based on your experiment results.
def score_to_band(score: float) -> SecurityTier:
    if score <= 30:
        return SecurityTier.BASELINE
    elif score <= 70:
        return SecurityTier.ELEVATED
    else:
        return SecurityTier.INTENSIVE


class HysteresisController:
    """
    Tracks recent risk scores and only changes the *active* tier once
    the new band has been consistently observed for `persistence` readings.
    """

    def __init__(self, persistence: int = 3, history_size: int = 10):
        """
        persistence: how many consecutive readings in a new band are needed
                     before we switch. Higher = more stable but slower to react.
        history_size: how many past readings we keep around (for debugging/logging).
        """
        self.persistence = persistence
        self.history = deque(maxlen=history_size)
        self.active_tier = SecurityTier.BASELINE
        self._candidate_tier = SecurityTier.BASELINE
        self._candidate_count = 0

    def update(self, score: float) -> SecurityTier:
        """
        Feed in a new risk score. Returns the ACTIVE tier (which may or may
        not have changed as a result of this reading).
        """
        self.history.append(score)
        new_band = score_to_band(score)

        if new_band == self.active_tier:
            # Already in this tier — reset any pending switch attempt.
            self._candidate_tier = self.active_tier
            self._candidate_count = 0
            return self.active_tier

        if new_band == self._candidate_tier:
            # Same candidate as last time — increment persistence counter.
            self._candidate_count += 1
        else:
            # New candidate band — start counting from 1.
            self._candidate_tier = new_band
            self._candidate_count = 1

        if self._candidate_count >= self.persistence:
            # The new band has held long enough — commit the switch.
            self.active_tier = self._candidate_tier
            self._candidate_count = 0

        return self.active_tier


if __name__ == "__main__":
    # Simulate a noisy score hovering around the Elevated/Intensive boundary (70).
    hc = HysteresisController(persistence=3)
    test_scores = [65, 72, 68, 74, 75, 76, 74, 40, 35, 20, 22]

    for s in test_scores:
        tier = hc.update(s)
        print(f"score={s:>3}  ->  active_tier={tier.value}")
