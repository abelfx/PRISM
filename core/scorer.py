"""
Main Python Coordinator and Entry Point for PRISM.

Called from MeTTa via Prolog Janus FFI:
  - Task priority ranking: (prism-score  ) -> scorer.score_candidate
  - Stage 0 premise pre-filtering: (prism-filter-beliefs   ) -> scorer.filter_beliefs
"""

import logging
from typing import Any, Dict, List, Union

from prism.core.config import DEFAULT_CONFIG
from prism.core.cache import ScoreCache
from prism.stage0.index import PremiseIndex
from prism.tier1.heuristic_v1 import compute_v1_score, extract_confidence

logger = logging.getLogger("prism.scorer")

_cache: ScoreCache = ScoreCache()
_stage0_index: PremiseIndex = PremiseIndex(config=DEFAULT_CONFIG.stage0)


def score_candidate(sentence: Any, goal: Any) -> Union[float, str]:
    """
    Main priority scoring entry point invoked by PriorityRankGoal.

    Inputs:
        sentence (Any): Candidate Sentence representation [Sentence, body, stamp].
        goal (Any): Derivation goal term (or None / empty tuple ()).

    Outputs:
        Union[float, str]: Numeric priority score on success, or string "Error"
        on exception to trigger graceful MeTTa fallback.

    What it does NOT handle:
        Does not perform MeTTa pattern matching or select tasks from queues.
    """
    try:
        if goal is None or goal == () or goal == "()" or goal == []:
            return extract_confidence(sentence, DEFAULT_CONFIG.tier1.default_confidence)

        return _cache.get_or_compute(
            sentence,
            goal,
            lambda s, g: compute_v1_score(s, g, DEFAULT_CONFIG.tier1),
        )
    except Exception as exc:
        try:
            logger.warning("Exception in score_candidate: %s", getattr(exc, 'args', str(exc)))
        except Exception:
            pass
        return "Error"


def filter_beliefs(candidate: Any, goal: Any, beliefs: Any) -> Any:
    """
    Stage 0 premise pre-filtering entry point invoked by PLN.Derive.

    Inputs:
        candidate (Any): Currently selected Sentence task.
        goal (Any): Derivation goal term.
        beliefs (Any): Buffer of candidate belief sentences (list or tuple).

    Outputs:
        Any: Filtered subset of beliefs relevant to candidate or goal,
        or the original beliefs on error/fallback.

    What it does NOT handle:
        Does not execute rule unifications or calculate conclusion truth values.
    """
    try:
        if not DEFAULT_CONFIG.stage0.enabled:
            return beliefs
        if not isinstance(beliefs, (list, tuple)):
            return beliefs

        return _stage0_index.filter_beliefs(candidate, goal, list(beliefs))
    except Exception as exc:
        try:
            logger.warning("Exception in filter_beliefs: %s. Falling back to full beliefs.", getattr(exc, 'args', str(exc)))
        except Exception:
            pass
        return beliefs


def clear_cache() -> str:
    """
    Reset the memoization cache between query executions.

    Inputs:
        None.

    Outputs:
        str: Status confirmation "OK".

    What it does NOT handle:
        Does not reset Stage 0 index or knowledge base contents.
    """
    _cache.clear()
    return "OK"


def cache_stats() -> Dict[str, Any]:
    """
    Retrieve memoization cache hit and miss statistics.

    Inputs:
        None.

    Outputs:
        Dict[str, Any]: Cache statistics dictionary.

    What it does NOT handle:
        Does not track inference step counts or search waste ratio.
    """
    return _cache.stats()
