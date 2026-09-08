"""
Score Memoization Cache for PRISM.

Mitigates the O((N - K) * N) FFI bottleneck during PLN queue pruning in LimitSize.
Caches numeric scores for (sentence, goal) pairs during derivation.
"""

from typing import Any, Callable, Dict, Tuple


class ScoreCache:
    """
    Thread-safe in-memory cache mapping (sentence_repr, goal_repr) -> score.
    Scores are invariant during sorting operations within a single derivation step.
    """

    def __init__(self):
        self._cache: Dict[Tuple[int, int], float] = {}
        self.hits: int = 0
        self.misses: int = 0

    @staticmethod
    def _hash_key(item: Any) -> int:
        """Create a stable hash key from arbitrary nested MeTTa/Python structures."""
        if isinstance(item, (int, float, str)):
            return hash(item)
        return hash(str(item))

    def get_or_compute(
        self, sentence: Any, goal: Any, compute_fn: Callable[[Any, Any], float]
    ) -> float:
        """
        Retrieve cached score or compute and store it.
        """
        key = (self._hash_key(sentence), self._hash_key(goal))
        if key in self._cache:
            self.hits += 1
            return self._cache[key]

        self.misses += 1
        score = compute_fn(sentence, goal)
        self._cache[key] = score
        return score

    def clear(self) -> None:
        """Reset the cache between derivation queries."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": f"{self.hit_ratio:.2%}",
        }
