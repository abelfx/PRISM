"""
PRISM Configuration Module.

Central repository for all hyperparameters, weights, thresholds, and queue sizes
used across PRISM tiers. No hardcoded constants should appear in algorithmic logic.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tier1Config:
    """
    Configuration parameters for Tier 1 Fast Scorer (v1 and v2).

    Inputs:
        alpha (float): Weight for structural atom overlap Jaccard score.
        beta (float): Weight for expected truth-value confidence.
        delta (float): Weight for derivation depth geometric discount.
        gamma (float): Geometric decay factor for derivation depth.
        default_confidence (float): Fallback confidence when parsing fails.
        empty_score (float): Sentinel score for empty candidate tuple.

    Outputs:
        Immutable configuration instance.

    What it does NOT handle:
        Does not execute scoring algorithms, does not parse MeTTa terms,
        and does not perform FFI conversions.
    """
    alpha: float = 0.65
    beta: float = 0.25
    delta: float = 0.10
    gamma: float = 0.90
    default_confidence: float = 0.5
    empty_score: float = -99999.0


@dataclass(frozen=True)
class Stage0Config:
    """
    Configuration parameters for Stage 0 Indexed Premise Pre-Filter.

    Inputs:
        enabled (bool): Whether Stage 0 pre-filtering is active.
        max_beliefs (int): Expected maximum belief buffer size.

    Outputs:
        Immutable configuration instance.

    What it does NOT handle:
        Does not manage index storage or execute unifications.
    """
    enabled: bool = True
    max_beliefs: int = 100


@dataclass(frozen=True)
class SearchConfig:
    """
    Configuration parameters for Learned A* / Best-First Search Engine.

    Inputs:
        max_steps (int): Maximum derivation expansion steps before termination.
        beam_width (int): Maximum number of top candidates expanded per node (top-k).
        cost_confidence_weight (float): Multiplier for uncertainty cost (1.0 - confidence).
        min_step_cost (float): Floor cost per deduction step to prevent 0-cost cycles.
        stall_threshold (float): Tier 1 score threshold below which state is deemed stalled.
        deduplicate_beliefs (bool): Whether to enforce closed-set state hashing.
        guided (bool): Whether to use Tier 1 heuristic guidance (A*) or uniform cost.
        use_stage0_filter (bool): Whether to pre-filter candidate premises using Stage 0.
        beam_threshold (float): Adaptive beam threshold; if > 0.0, expands candidates with score >= top_score - beam_threshold.
        task_selection_k (int): Number of top-priority tasks to expand per state node.

    Outputs:
        Immutable configuration instance.

    What it does NOT handle:
        Does not maintain the open queue, does not fire inference rules,
        and does not perform FFI conversions.
    """
    max_steps: int = 100
    beam_width: int = 5
    cost_confidence_weight: float = 1.0
    min_step_cost: float = 0.01
    stall_threshold: float = 0.15
    deduplicate_beliefs: bool = True
    guided: bool = True
    use_stage0_filter: bool = True
    beam_threshold: float = 0.0
    task_selection_k: int = 3


@dataclass(frozen=True)
class PrismConfig:
    """
    Top-level master configuration container for PRISM.

    Inputs:
        tier1 (Tier1Config): Configuration for Tier 1 fast scorer.
        stage0 (Stage0Config): Configuration for Stage 0 premise pre-filter.
        search (SearchConfig): Configuration for Learned A* search engine.

    Outputs:
        Master configuration instance.

    What it does NOT handle:
        Does not perform derivation or interface directly with FFI.
    """
    tier1: Tier1Config = Tier1Config()
    stage0: Stage0Config = Stage0Config()
    search: SearchConfig = SearchConfig()


# Global default configuration instance
DEFAULT_CONFIG = PrismConfig()
