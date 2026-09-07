"""
Main Python Scorer Entry Point for PRISM.
Called from MeTTa via: (py-call (scorer.score_candidate $sentence $Goal))
"""

import re
from typing import Any, Set
from prism.cache import ScoreCache

_cache = ScoreCache()


def _atomize(expr: Any) -> Set[str]:
    """
    Extract individual atomic tokens from a nested expression or string representation.
    Handles lists, tuples, and stringified MeTTa expressions.
    """
    if isinstance(expr, str):
        # Extract alphanumeric words and hyphens (e.g. 'Inheritance', 'Alice', 'Ancestor-of-Bob')
        tokens = re.findall(r"[A-Za-z0-9_\-]+", expr)
        # Filter out pure numbers and MeTTa structural keywords
        return {
            t
            for t in tokens
            if not re.match(r"^-?\d+(\.\d+)?$", t)
            and t not in {"Sentence", "stv"}
        }
    if isinstance(expr, (list, tuple)):
        atoms: Set[str] = set()
        for sub in expr:
            atoms |= _atomize(sub)
        return atoms
    return {str(expr)}


def _extract_confidence(sentence: Any) -> float:
    """
    Safely extract confidence from a Sentence representation.
    Handles:
      - nested lists/tuples: ['Sentence', [statement, ['stv', strength, confidence]], stamp]
      - string fallback regex matching: '(stv <f> <c>)'
    """
    try:
        if isinstance(sentence, (list, tuple)) and len(sentence) >= 2:
            body = sentence[1]
            if isinstance(body, (list, tuple)) and len(body) >= 2:
                tv = body[1]
                if isinstance(tv, (list, tuple)) and len(tv) >= 3:
                    return float(tv[2])
        # Fallback to regex on string representation
        text = str(sentence)
        match = re.search(r"stv\s+[\d\.\-eE]+\s+([\d\.\-eE]+)", text)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return 0.5


def _compute_v1_score(sentence: Any, goal: Any) -> float:
    """
    Tier 1 v1 Symbolic/Structural Heuristic:
    Score = alpha * Overlap(S, G) + beta * Confidence
    """
    s_atoms = _atomize(sentence)
    g_atoms = _atomize(goal)
    conf = _extract_confidence(sentence)

    if not g_atoms:
        overlap = 0.0
    else:
        overlap = len(s_atoms & g_atoms) / len(g_atoms)

    alpha = 0.7
    beta = 0.3
    return (alpha * overlap) + (beta * conf)


def score_candidate(sentence: Any, goal: Any) -> Any:
    """
    Main entry point invoked by PriorityRankGoal.
    Returns float score on success, or string "Error" on any exception
    to trigger the MeTTa-side fallback to raw confidence.
    """
    try:
        if goal is None or goal == () or goal == "()" or goal == []:
            return _extract_confidence(sentence)

        return _cache.get_or_compute(
            sentence, goal, lambda s, g: _compute_v1_score(s, g)
        )
    except Exception as exc:
        # Prevent Janus from crashing SWI-Prolog; trigger MeTTa fallback
        print(f"[PRISM scorer warning] Exception in score_candidate: {exc}")
        return "Error"


def clear_cache() -> str:
    """Reset the memoization cache between query executions."""
    _cache.clear()
    return "OK"


def cache_stats() -> Any:
    """Return dictionary of cache hits, misses, and hit ratio."""
    return _cache.stats()
