"""Runtime adapter for a trained Week 11 Tier 1 v2 checkpoint."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from prism.tier1.heuristic_v1 import extract_confidence, extract_depth
from prism.training.model import Tier1V2Model


@lru_cache(maxsize=4)
def load_model(path: str) -> Tier1V2Model:
    """Load and memoize an immutable inference checkpoint."""
    return Tier1V2Model.load(Path(path))


def _strength(sentence: Any) -> float:
    try:
        if isinstance(sentence, (list, tuple)):
            return float(sentence[1][1][1])
        import re
        match = re.search(r"stv\s+([\d.\-eE]+)", str(sentence))
        return float(match.group(1)) if match else 1.0
    except (IndexError, TypeError, ValueError):
        return 1.0


def compute_v2_score(
    sentence: Any,
    goal: Any,
    model_path: str,
    queue_position: int = 0,
    candidate_pool_size: int = 1,
) -> float:
    """Score one candidate, optionally including its preliminary queue rank."""
    return load_model(model_path).score(
        candidate=str(sentence),
        goal=str(goal),
        strength=_strength(sentence),
        confidence=extract_confidence(sentence, 0.5),
        depth=extract_depth(sentence),
        queue_position=queue_position,
        candidate_pool_size=candidate_pool_size,
    )
