from benchmarks.domains.transitive_chain import generate_with_distractors
from benchmarks.evaluate_scaling_generalization import (
    _search_metrics,
    aggregate_trials,
    scaling_exponent,
    stage0_pair_frontier,
)
from prism.search.engine import SearchResult
from prism.search.state import SearchNode
from benchmarks.evaluate_search_comparison import format_spec_facts


def test_stage0_pair_frontier_reduces_cartesian_pairs():
    spec = generate_with_distractors(depth=4, n_distractors=20, seed=42)
    facts = format_spec_facts(spec)
    counts = stage0_pair_frontier(facts, facts, spec["goal"])
    assert counts["raw_pairs"] == len(facts) ** 2
    assert counts["filtered_pairs"] < counts["raw_pairs"]
    assert 0.0 < counts["reduction"] <= 1.0


def test_scaling_exponent_detects_constant_and_superlinear_growth():
    assert scaling_exponent([(10, 2), (20, 2), (40, 2), (80, 2)]) == 0.0
    assert scaling_exponent([(10, 1), (20, 4), (40, 16), (80, 64)]) > 1.0


def test_waste_counts_actions_absent_from_final_evidence():
    useful = ["Sentence", [["Inheritance", "A", "C"], ["stv", 0.8, 0.7]], ["1", "2"]]
    wasted = ["Sentence", [["Inheritance", "D0", "D2"], ["stv", 0.8, 0.7]], ["9", "10"]]
    goal = ["Sentence", [["Inheritance", "A", "Z"], ["stv", 0.7, 0.6]], ["1", "2", "3"]]
    nodes = [
        SearchNode(1, [], [], 0.0, 0.0, 0.0, 0, None, None, 0),
        SearchNode(2, [], [], 0.0, 0.0, 0.0, 1, 1, wasted, 1),
        SearchNode(3, [], [], 0.0, 0.0, 0.0, 2, 2, useful, 2),
    ]
    result = SearchResult(True, nodes[-1], nodes, goal, 3, 3, 3, 0.01)
    metrics = _search_metrics(result)
    assert metrics["proof_actions"] == 1
    assert metrics["wasted_expansions"] == 1


def test_random_trial_aggregate_preserves_success_and_waste_range():
    trials = [
        {"success": True, "steps": 3, "wasted_expansions": 1},
        {"success": False, "steps": 8, "wasted_expansions": 7},
        {"success": False, "steps": 8, "wasted_expansions": 4},
    ]
    result = aggregate_trials(trials)
    assert result["trials"] == 3
    assert result["successes"] == 1
    assert result["success_rate"] == 0.333333
    assert result["min_wasted_expansions"] == 1
    assert result["max_wasted_expansions"] == 7
