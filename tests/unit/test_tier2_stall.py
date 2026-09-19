"""
Unit tests for PRISM Tier 2 Stall Detector.
Verifies GATE-7.1: Plateau stall detection, depth triggering, and cooldown logic.
"""

from prism.core.config import Tier2Config
from prism.tier2.stall_detector import StallDetector


def test_stall_detector_counter_progression():
    """Verify consecutive low score counter increments and resets properly."""
    cfg = Tier2Config(stall_threshold=0.20, stall_steps=5, cooldown_steps=3)
    detector = StallDetector(cfg)

    assert not detector.check_stall(top_score=0.15)
    assert detector.consecutive_low_scores == 1

    assert not detector.check_stall(top_score=0.18)
    assert detector.consecutive_low_scores == 2

    # High score resets counter
    assert not detector.check_stall(top_score=0.85)
    assert detector.consecutive_low_scores == 0


def test_stall_detector_triggers_on_k_steps():
    """Verify GATE-7.1: Detects stall when low scores persist for k consecutive steps."""
    cfg = Tier2Config(stall_threshold=0.20, stall_steps=5, cooldown_steps=3)
    detector = StallDetector(cfg)

    # 4 low steps: no stall yet
    for _ in range(4):
        assert not detector.check_stall(top_score=0.10)

    # 5th low step: triggers stall
    assert detector.check_stall(top_score=0.10)
    assert detector.consecutive_low_scores == 5


def test_stall_detector_triggers_on_depth():
    """Verify stall triggers proactively when search depth exceeds threshold."""
    cfg = Tier2Config(stall_threshold=0.20, stall_steps=5, max_depth_threshold=10)
    detector = StallDetector(cfg)

    # High score but deep node
    assert detector.check_stall(top_score=0.50, current_depth=10)


def test_stall_detector_cooldown_prevents_retrigger():
    """Verify cooldown period blocks immediate re-invocation of Tier 2."""
    cfg = Tier2Config(stall_threshold=0.20, stall_steps=3, cooldown_steps=4)
    detector = StallDetector(cfg)

    # Trigger stall
    for _ in range(3):
        detector.check_stall(top_score=0.10)
    assert detector.check_stall(top_score=0.10)

    # Record that Tier 2 was invoked
    detector.record_invocation()
    assert detector.total_stalls_triggered == 1
    assert detector.cooldown_remaining == 4
    assert detector.consecutive_low_scores == 0

    # During cooldown, check_stall must return False even on low scores
    for i in range(4):
        assert not detector.check_stall(top_score=0.05)

    # After cooldown expires and 3 more low scores accumulate, it triggers again
    for _ in range(2):
        assert not detector.check_stall(top_score=0.05)
    assert detector.check_stall(top_score=0.05)


def test_stall_detector_clean_chain_no_trigger():
    """Verify 0 false triggers on clean reasoning steps (GATE-7.1)."""
    cfg = Tier2Config(stall_threshold=0.20, stall_steps=5)
    detector = StallDetector(cfg)

    # Simulate 20 high-confidence derivation steps
    for _ in range(20):
        assert not detector.check_stall(top_score=0.75, current_depth=2)

    assert detector.total_stalls_triggered == 0
