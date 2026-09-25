"""Safe boundary helpers for optional PRISM search-control components."""

from __future__ import annotations

import logging
import math
from numbers import Real
from typing import Any, Callable, Optional, Tuple

from prism.core.cache import ScoreCache
from prism.tier1.heuristic_v1 import extract_confidence

logger = logging.getLogger(__name__)


def safe_cached_score(
    cache: ScoreCache,
    sentence: Any,
    goal: Any,
    compute_fn: Callable[[Any, Any], float],
    *,
    default_confidence: float = 0.5,
) -> Tuple[float, Optional[str]]:
    """Return a valid score or deterministic confidence-only fallback."""
    fallback = min(1.0, max(0.0, float(extract_confidence(sentence, default_confidence))))
    try:
        score = cache.get_or_compute(sentence, goal, compute_fn)
        if isinstance(score, bool) or not isinstance(score, Real):
            raise ValueError("scorer returned a non-numeric value")
        score = float(score)
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError("scorer returned a non-finite or out-of-range value")
        return score, None
    except Exception as exc:
        diagnostic = f"tier1_confidence_fallback: {type(exc).__name__}: {exc}"
        logger.warning(diagnostic)
        return fallback, diagnostic
