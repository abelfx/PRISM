"""
Stall Detection Subsystem for PRISM Tier 2.

Monitors search progression at each node expansion. Detects when forward
exploration has stalled on low-promise candidates or exceeded depth thresholds,
signaling the need for high-level LLM strategic guidance.
"""

from typing import Optional
from prism.core.config import Tier2Config


class StallDetector:
    """
    Monitors search expansion to detect stalled reasoning states.

    Stall is declared when:
    1. Heuristic scores remain below stall_threshold for >= stall_steps consecutive steps.
    2. Search depth exceeds max_depth_threshold.

    Includes a cooldown buffer to prevent repeated triggers on consecutive steps.
    """

    def __init__(self, config: Optional[Tier2Config] = None):
        cfg = config or Tier2Config()
        self.stall_threshold: float = cfg.stall_threshold
        self.stall_steps: int = cfg.stall_steps
        self.max_depth_threshold: int = cfg.max_depth_threshold
        self.cooldown_steps: int = cfg.cooldown_steps

        self.consecutive_low_scores: int = 0
        self.cooldown_remaining: int = 0
        self.total_stalls_triggered: int = 0

    def check_stall(self, top_score: float, current_depth: int = 0) -> bool:
        """
        Evaluate whether the current search state qualifies as stalled.

        Args:
            top_score: Highest Tier 1 heuristic score among current candidates.
            current_depth: Current deduction depth of the expanding node.

        Returns:
            bool: True if stall conditions are met and cooldown is expired.
        """
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return False

        if top_score < self.stall_threshold:
            self.consecutive_low_scores += 1
        else:
            self.consecutive_low_scores = 0

        is_plateau = self.consecutive_low_scores >= self.stall_steps
        is_deep = current_depth >= self.max_depth_threshold

        if is_plateau or is_deep:
            return True

        return False

    def record_invocation(self) -> None:
        """
        Record that Tier 2 was invoked.
        Resets low-score counter and starts cooldown period.
        """
        self.consecutive_low_scores = 0
        self.cooldown_remaining = self.cooldown_steps
        self.total_stalls_triggered += 1

    def reset(self) -> None:
        """Reset all counters and cooldown state to initial values."""
        self.consecutive_low_scores = 0
        self.cooldown_remaining = 0
        self.total_stalls_triggered = 0
