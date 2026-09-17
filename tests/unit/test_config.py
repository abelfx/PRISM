"""
Unit tests for PRISM configuration module.
Verifies defaults, immutability, and parameter boundaries.
"""

import pytest
from prism.core.config import (
    DEFAULT_CONFIG,
    PrismConfig,
    SearchConfig,
    Stage0Config,
    Tier1Config,
    Tier2Config,
    BidirectionalConfig,
)


def test_tier1_config_defaults():
    """Verify default values specified in PRISM Implementation Spec §5.1."""
    t1 = Tier1Config()
    assert t1.alpha == 0.65
    assert t1.beta == 0.25
    assert t1.delta == 0.10
    assert t1.gamma == 0.9
    assert t1.default_confidence == 0.5
    assert t1.empty_score == -99999.0


def test_tier1_config_immutability():
    """Ensure configuration is immutable to prevent accidental logic mutations."""
    t1 = Tier1Config()
    with pytest.raises(Exception):
        t1.alpha = 0.8  # type: ignore


def test_stage0_config_defaults():
    """Verify Stage 0 configuration defaults."""
    s0 = Stage0Config()
    assert s0.enabled is True
    assert s0.max_beliefs == 100


def test_search_config_defaults():
    """Verify SearchConfig defaults per Week 5 specification."""
    sc = SearchConfig()
    assert sc.max_steps == 100
    assert sc.beam_width == 5
    assert sc.cost_confidence_weight == 1.0
    assert sc.min_step_cost == 0.01
    assert sc.stall_threshold == 0.15
    assert sc.deduplicate_beliefs is True
    assert sc.guided is True
    assert sc.use_stage0_filter is True
    assert sc.beam_threshold == 0.0
    assert sc.task_selection_k == 3
    assert sc.enable_tier2 is False


def test_search_config_immutability():
    """Ensure SearchConfig is frozen immutable."""
    sc = SearchConfig()
    with pytest.raises(Exception):
        sc.beam_width = 10  # type: ignore


def test_tier2_config_defaults():
    """Verify Tier 2 Strategic LLM configuration defaults."""
    t2 = Tier2Config()
    assert t2.enabled is True
    assert t2.stall_threshold == 0.20
    assert t2.stall_steps == 5
    assert t2.max_depth_threshold == 10
    assert t2.cooldown_steps == 8
    assert t2.backend == "mock"
    assert ":free" in t2.model_name


def test_tier2_config_immutability():
    """Ensure Tier2Config is frozen immutable."""
    t2 = Tier2Config()
    with pytest.raises(Exception):
        t2.stall_threshold = 0.50  # type: ignore


def test_master_config_structure():
    """Verify master PrismConfig integrates sub-configs."""
    assert DEFAULT_CONFIG.tier1.alpha == 0.65
    assert DEFAULT_CONFIG.stage0.enabled is True
    assert DEFAULT_CONFIG.search.beam_width == 5
    assert DEFAULT_CONFIG.tier2.enabled is True
    assert DEFAULT_CONFIG.bidirectional.connection_check_interval == 1
    assert DEFAULT_CONFIG.bidirectional.max_backward_depth == 10


def test_bidirectional_config_defaults():
    cfg = BidirectionalConfig()
    assert cfg.connection_check_interval == 1
    assert cfg.max_backward_depth == 10
    assert cfg.forward_backward_ratio == 1.0
    assert cfg.backward_beam_width == 5



