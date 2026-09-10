"""
Unit tests for PRISM Multi-Path Diamond DAG domain generator.
Verifies topology generation, boundary enforcement, distractor injection,
and solution path classification.
"""

import pytest
from prism.benchmarks.domains.multipath_dag import (
    classify_diamond_solution,
    generate_diamond,
    generate_diamond_metta_content,
    generate_diamond_with_distractors,
)


def test_diamond_parameter_validation():
    """Verify that invalid depths raise ValueError."""
    with pytest.raises(ValueError):
        generate_diamond(depth_short=1, depth_long=5)

    with pytest.raises(ValueError):
        generate_diamond(depth_short=4, depth_long=4)

    with pytest.raises(ValueError):
        generate_diamond(depth_short=5, depth_long=3)


def test_diamond_structure_and_nodes():
    """Verify nodes and facts for a 2-shortcut vs 4-longpath diamond."""
    spec = generate_diamond(depth_short=2, depth_long=4)

    assert spec["domain_type"] == "diamond_dag"
    assert spec["start_node"] == "A"
    assert spec["goal_node"] == "Z"
    assert spec["goal"] == "(Inheritance A Z)"

    # Shortcut: A -> S1 -> Z (depth 2 = 2 facts)
    assert spec["shortcut_nodes"] == ["A", "S1", "Z"]
    assert len(spec["shortcut_facts"]) == 2

    # Long path: A -> L1 -> L2 -> L3 -> Z (depth 4 = 4 facts)
    assert spec["long_nodes"] == ["A", "L1", "L2", "L3", "Z"]
    assert len(spec["long_facts"]) == 4

    # Disjoint evidence IDs
    shortcut_eids = spec["shortcut_evidence_ids"]
    long_eids = spec["long_evidence_ids"]
    assert len(set(shortcut_eids).intersection(set(long_eids))) == 0
    assert spec["total_facts"] == 6


def test_diamond_with_distractors():
    """Verify distractor injection and seed reproducibility."""
    spec1 = generate_diamond_with_distractors(
        depth_short=3, depth_long=6, n_distractors=15, seed=123
    )
    spec2 = generate_diamond_with_distractors(
        depth_short=3, depth_long=6, n_distractors=15, seed=123
    )

    assert len(spec1["distractor_facts"]) == 15
    assert spec1["total_facts"] == 3 + 6 + 15
    assert spec1["distractor_facts"] == spec2["distractor_facts"]


def test_classify_diamond_solution():
    """Verify classification of solution stamps into SHORTCUT, LONG_PATH, or MIXED."""
    spec = generate_diamond(depth_short=2, depth_long=4)
    # Shortcut EIDs: ['1', '2']
    # Long EIDs: ['3', '4', '5', '6']

    assert classify_diamond_solution(["1", "2"], spec) == "SHORTCUT"
    assert classify_diamond_solution(["3", "4", "5", "6"], spec) == "LONG_PATH"
    assert classify_diamond_solution(["1", "4"], spec) == "MIXED"
    assert classify_diamond_solution([], spec) == "UNKNOWN"
    assert classify_diamond_solution(None, spec) == "UNKNOWN"
    assert classify_diamond_solution(["99"], spec) == "UNKNOWN"


def test_generate_diamond_metta_content():
    """Verify rendering of MeTTa benchmark file with both guided and unguided options."""
    spec = generate_diamond(depth_short=2, depth_long=3)

    guided_content = generate_diamond_metta_content(spec, guided=True)
    assert "(PLN.Query (kb) (Inheritance A Z)" in guided_content
    assert "(Sentence ((Inheritance A S1)" in guided_content

    unguided_content = generate_diamond_metta_content(spec, guided=False)
    assert "PLN.Derive (kb) (kb) 1" in unguided_content
    assert "BENCHMARK_RESULT:" in unguided_content
