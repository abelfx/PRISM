"""
Unit tests for PRISM backward search primitives (§9.2, §9.3).

Verifies subgoal decomposition, intermediate variable grounding, and meet-in-the-middle
connection detection.
"""

import pytest
from prism.search.backward import (
    BackwardCandidate,
    backward_step,
    check_connection,
)


def test_backward_step_forward_anchor():
    """
    Given goal (Inheritance A Z) and belief (Inheritance A B):
    backward_step should hypothesize intermediate B with missing premise (Inheritance B Z).
    """
    beliefs = [
        ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]],
        ["Sentence", [["Inheritance", "X", "Y"], ["stv", 0.9, 0.9]], ["2"]],
    ]
    goal = ["Inheritance", "A", "Z"]

    candidates = backward_step(goal, beliefs)
    assert len(candidates) >= 1

    # Look for candidate utilizing intermediate B
    b_cand = [c for c in candidates if any(p[1][0] == ["Inheritance", "A", "B"] for p in c.available_premises)]
    assert len(b_cand) == 1
    cand = b_cand[0]
    assert cand.rule_name == "Deduction"
    assert cand.completeness == 0.5
    assert len(cand.available_premises) == 1
    assert len(cand.missing_premises) == 1
    assert cand.missing_premises[0][1][0] == ["Inheritance", "B", "Z"]


def test_backward_step_backward_anchor():
    """
    Given goal (Inheritance A Z) and belief (Inheritance Y Z):
    backward_step should hypothesize intermediate Y with missing premise (Inheritance A Y).
    """
    beliefs = [
        ["Sentence", [["Inheritance", "Y", "Z"], ["stv", 0.9, 0.9]], ["10"]],
    ]
    goal = ["Inheritance", "A", "Z"]

    candidates = backward_step(goal, beliefs)
    assert len(candidates) >= 1
    cand = candidates[0]
    assert cand.completeness == 0.5
    assert cand.available_premises[0][1][0] == ["Inheritance", "Y", "Z"]
    assert cand.missing_premises[0][1][0] == ["Inheritance", "A", "Y"]


def test_backward_step_both_anchors_complete():
    """
    When both (Inheritance A M) and (Inheritance M Z) exist in beliefs:
    candidate completeness should be 1.0.
    """
    beliefs = [
        ["Sentence", [["Inheritance", "A", "M"], ["stv", 0.9, 0.9]], ["1"]],
        ["Sentence", [["Inheritance", "M", "Z"], ["stv", 0.9, 0.9]], ["2"]],
    ]
    goal = ["Inheritance", "A", "Z"]

    candidates = backward_step(goal, beliefs)
    assert len(candidates) >= 1
    best = candidates[0]
    assert best.completeness == 1.0
    assert len(best.missing_premises) == 0
    assert len(best.available_premises) == 2


def test_check_connection_success():
    """Test successful bidirectional connection detection."""
    forward_beliefs = [
        ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]],
        ["Sentence", [["Inheritance", "A", "M"], ["stv", 0.81, 0.72]], ["1", "2"]],
    ]
    backward_subgoals = [
        ["Sentence", [["Inheritance", "A", "M"], ["stv", 1.0, 0.9]], []],
        ["Sentence", [["Inheritance", "M", "Z"], ["stv", 1.0, 0.9]], []],
    ]

    res = check_connection(forward_beliefs, backward_subgoals)
    assert res is not None
    matched_belief, matched_subgoal = res
    assert matched_belief[1][0] == ["Inheritance", "A", "M"]
    assert matched_subgoal[1][0] == ["Inheritance", "A", "M"]


def test_check_connection_no_match():
    """Test connection detection when no subgoal is satisfied."""
    forward_beliefs = [
        ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]],
    ]
    backward_subgoals = [
        ["Sentence", [["Inheritance", "M", "Z"], ["stv", 1.0, 0.9]], []],
    ]

    res = check_connection(forward_beliefs, backward_subgoals)
    assert res is None
