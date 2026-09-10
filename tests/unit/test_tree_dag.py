"""
Unit tests for PRISM Tree & Conjunction Domain Generator.
Verifies multi-branch DAG creation, junction node routing, distractor injection,
and conjunctive solution verification.
"""

import pytest
from prism.benchmarks.domains.tree_dag import (
    generate_tree_conjunction,
    generate_tree_metta_content,
    generate_tree_with_distractors,
    verify_tree_conjunction_solution,
)


def test_tree_conjunction_validation():
    """Verify that invalid branch depths raise ValueError."""
    with pytest.raises(ValueError):
        generate_tree_conjunction(depth_left=0, depth_right=2)

    with pytest.raises(ValueError):
        generate_tree_conjunction(depth_left=2, depth_right=0)


def test_tree_conjunction_structure():
    """Verify nodes, branches, and junction routing for depth (2, 2)."""
    spec = generate_tree_conjunction(depth_left=2, depth_right=2)

    assert spec["domain_type"] == "tree_conjunction"
    assert spec["start_node"] == "A"
    assert spec["junction_node"] == "M"
    assert spec["goal_node"] == "Z"
    assert spec["goal"] == "(Inheritance A Z)"

    # Left: A -> L1 -> M (2 facts)
    assert spec["left_nodes"] == ["A", "L1", "M"]
    assert len(spec["left_facts"]) == 2

    # Right: M -> R1 -> Z (2 facts)
    assert spec["right_nodes"] == ["M", "R1", "Z"]
    assert len(spec["right_facts"]) == 2

    # Evidence IDs disjoint
    left_eids = set(spec["left_evidence_ids"])
    right_eids = set(spec["right_evidence_ids"])
    assert len(left_eids.intersection(right_eids)) == 0
    assert spec["total_facts"] == 4


def test_tree_with_distractors():
    """Verify distractor injection and seed reproducibility."""
    spec1 = generate_tree_with_distractors(
        depth_left=2, depth_right=3, n_distractors=10, seed=42
    )
    spec2 = generate_tree_with_distractors(
        depth_left=2, depth_right=3, n_distractors=10, seed=42
    )

    assert len(spec1["distractor_facts"]) == 10
    assert spec1["total_facts"] == 2 + 3 + 10
    assert spec1["distractor_facts"] == spec2["distractor_facts"]


def test_verify_tree_conjunction_solution():
    """Verify solution requires premises from both branches."""
    spec = generate_tree_conjunction(depth_left=2, depth_right=2)
    # Left EIDs: ['1', '2']
    # Right EIDs: ['3', '4']

    # Both branches present -> Valid conjunctive solution
    assert verify_tree_conjunction_solution(["1", "2", "3", "4"], spec) is True
    assert verify_tree_conjunction_solution(["1", "4"], spec) is True

    # Only one branch present -> Invalid
    assert verify_tree_conjunction_solution(["1", "2"], spec) is False
    assert verify_tree_conjunction_solution(["3", "4"], spec) is False

    # Empty or None -> Invalid
    assert verify_tree_conjunction_solution([], spec) is False
    assert verify_tree_conjunction_solution(None, spec) is False


def test_generate_tree_metta_content():
    """Verify rendering of MeTTa benchmark file for tree conjunction."""
    spec = generate_tree_conjunction(depth_left=1, depth_right=1)
    content = generate_tree_metta_content(spec, guided=True)

    assert "(PLN.Query (kb) (Inheritance A Z)" in content
    assert "(Sentence ((Inheritance A M)" in content
    assert "(Sentence ((Inheritance M Z)" in content
