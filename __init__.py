"""
PRISM: Programmable Reduction & Inference Search Manager.
A learned inference-control layer for Probabilistic Logic Networks (PLN).
"""

__version__ = "0.1.0"

from prism.core.config import DEFAULT_CONFIG, PrismConfig, Stage0Config, Tier1Config
from prism.core.cache import ScoreCache
from prism.core.scorer import filter_beliefs, score_candidate
from prism.stage0.index import PremiseIndex
from prism.tier1.heuristic_v1 import compute_v1_score

__all__ = [
    "DEFAULT_CONFIG",
    "PrismConfig",
    "Tier1Config",
    "Stage0Config",
    "PremiseIndex",
    "ScoreCache",
    "compute_v1_score",
    "score_candidate",
    "filter_beliefs",
]
