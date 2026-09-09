"""
Unit tests for PRISM Scorer Coordinator.
Verifies caching, fallback logic, error handling, and Stage 0 belief filtering.
"""

from prism.core.scorer import (
    cache_stats,
    clear_cache,
    filter_beliefs,
    score_candidate,
)


def setup_function():
    clear_cache()


def test_score_candidate_empty_goal():
    """When goal is empty or None, returns raw confidence."""
    cand = ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.77]], [1]]
    assert score_candidate(cand, None) == 0.77
    assert score_candidate(cand, ()) == 0.77
    assert score_candidate(cand, "()") == 0.77
    assert score_candidate(cand, []) == 0.77


def test_score_candidate_with_goal_and_cache():
    """With goal, returns calculated score and uses memoization cache."""
    cand = ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.85]], [1]]
    goal = ['Inheritance', 'A', 'C']

    s1 = score_candidate(cand, goal)
    assert isinstance(s1, float)
    assert s1 > 0.0

    stats1 = cache_stats()
    assert stats1['misses'] == 1
    assert stats1['hits'] == 0

    # Repeat call should hit cache
    s2 = score_candidate(cand, goal)
    assert s2 == s1
    stats2 = cache_stats()
    assert stats2['hits'] == 1


def test_score_candidate_error_fallback():
    """When an unexpected error occurs during calculation, returns 'Error'."""
    # An object that raises an exception when processed
    class BrokenObject:
        def __str__(self):
            raise RuntimeError("Simulated error")

    res = score_candidate(BrokenObject(), ['Goal'])
    assert res == "Error"


def test_filter_beliefs_stage0_filtering():
    """Verify filter_beliefs filters distractors and preserves on-path beliefs."""
    cand = ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.9]], [1]]
    goal = ['Inheritance', 'A', 'F']

    on_path = ['Sentence', [['Inheritance', 'B', 'C'], ['stv', 0.9, 0.9]], [2]]
    distractor = ['Sentence', [['Inheritance', 'D1', 'D2'], ['stv', 0.9, 0.9]], [3]]
    beliefs = [on_path, distractor]

    res = filter_beliefs(cand, goal, beliefs)
    assert on_path in res
    assert distractor not in res


def test_filter_beliefs_empty_goal():
    """When goal and candidate are empty, returns beliefs unchanged."""
    b1 = ['Sentence', [['Inheritance', 'D1', 'D2'], ['stv', 0.9, 0.9]], [1]]
    beliefs = [b1]
    res = filter_beliefs((), (), beliefs)
    assert res == beliefs


def test_filter_beliefs_error_safety():
    """When filtering encounters an error, gracefully returns all beliefs."""
    fallback = filter_beliefs(['Cand'], ['Goal'], "not_a_list")
    assert fallback == "not_a_list"


