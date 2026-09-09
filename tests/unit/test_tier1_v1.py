"""
Unit tests for PRISM Tier 1 v1 Symbolic Heuristic Scorer.
Verifies atomization, confidence extraction, depth extraction, and score computation.
"""

import pytest
from prism.core.config import Tier1Config
from prism.tier1.heuristic_v1 import (
    compute_depth_discount,
    compute_overlap,
    compute_v1_score,
    extract_atoms,
    extract_confidence,
    extract_depth,
)


def test_extract_atoms():
    """Verify atom extraction filters numbers and keywords."""
    expr = ['Sentence', [['Inheritance', 'Alice', 'Mortal'], ['stv', 0.9, 0.8]], [1]]
    atoms = extract_atoms(expr)
    assert 'Alice' in atoms
    assert 'Mortal' in atoms
    assert 'Inheritance' in atoms
    assert 'Sentence' not in atoms
    assert 'stv' not in atoms
    assert '0.9' not in atoms


def test_extract_confidence():
    """Verify extraction of confidence from structured list and fallback strings."""
    cfg = Tier1Config()
    # Structured sentence
    s1 = ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.77]], [1]]
    assert extract_confidence(s1, cfg.default_confidence) == 0.77

    # Stringified fallback
    s2 = "(Sentence ((Inheritance A B) (stv 0.9 0.82)) (1))"
    assert extract_confidence(s2, cfg.default_confidence) == 0.82

    # Malformed sentence falls back to default
    s3 = ['Invalid', 'Format']
    assert extract_confidence(s3, cfg.default_confidence) == cfg.default_confidence


def test_extract_depth():
    """Verify derivation depth extracted from evidence stamps."""
    # Base premise with 1 evidence stamp -> depth 0
    s_base = ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.9]], [1]]
    assert extract_depth(s_base) == 0

    # 1-step derivation with 2 premises combined -> depth 1
    s_step1 = ['Sentence', [['Inheritance', 'A', 'C'], ['stv', 0.81, 0.7]], [1, 2]]
    assert extract_depth(s_step1) == 1

    # 2-step derivation with 3 premises combined -> depth 2
    s_step2 = ['Sentence', [['Inheritance', 'A', 'D'], ['stv', 0.72, 0.5]], [1, 2, 3]]
    assert extract_depth(s_step2) == 2

    # Empty stamp or non-list -> depth 0
    assert extract_depth(['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.9]], []]) == 0
    assert extract_depth('malformed') == 0


def test_compute_overlap():
    """Verify Jaccard overlap calculation."""
    s_atoms = {'Inheritance', 'Alice', 'Mortal'}
    g_atoms = {'Inheritance', 'Alice', 'Mortal'}
    assert compute_overlap(s_atoms, g_atoms) == 1.0

    g_atoms_disjoint = {'Similarity', 'Bob', 'Robot'}
    assert compute_overlap(s_atoms, g_atoms_disjoint) == 0.0

    # Partial overlap: 'Inheritance' and 'Alice' match out of 3 goal atoms
    g_atoms_partial = {'Alice', 'Human'}
    assert pytest.approx(compute_overlap({'Alice', 'Mortal'}, g_atoms_partial), 0.001) == 1.0 / 2.0

    # Empty goal atoms
    assert compute_overlap(s_atoms, set()) == 0.0


def test_compute_depth_discount():
    """Verify geometric depth discount formula: delta * (gamma ^ depth)."""
    cfg = Tier1Config(delta=0.2, gamma=0.9)
    # depth 0: 0.2 * 1.0 = 0.2
    assert pytest.approx(compute_depth_discount(0, cfg.delta, cfg.gamma)) == 0.2
    # depth 1: 0.2 * 0.9 = 0.18
    assert pytest.approx(compute_depth_discount(1, cfg.delta, cfg.gamma)) == 0.18
    # depth 2: 0.2 * 0.81 = 0.162
    assert pytest.approx(compute_depth_discount(2, cfg.delta, cfg.gamma)) == 0.162


def test_compute_v1_score():
    """Verify composite score and that shallower derivations outscore deeper ones."""
    cfg = Tier1Config(alpha=0.5, beta=0.3, delta=0.2, gamma=0.9)
    goal = ['Inheritance', 'Alice', 'Mortal']

    # Candidate 1: base fact (depth 0), overlap 2/3, conf 0.8
    cand_shallow = ['Sentence', [['Inheritance', 'Alice', 'Person'], ['stv', 0.9, 0.8]], [1]]
    score_shallow = compute_v1_score(cand_shallow, goal, cfg)

    # Candidate 2: 2-step derivation (depth 2), same overlap (2/3) and conf (0.8)
    cand_deep = ['Sentence', [['Inheritance', 'Alice', 'Person'], ['stv', 0.9, 0.8]], [1, 2, 3]]
    score_deep = compute_v1_score(cand_deep, goal, cfg)

    # Shallow derivation must have strictly higher score due to depth discount
    assert score_shallow > score_deep
    # Verify expected score for shallow: 0.5 * (2/3) + 0.3 * 0.8 + 0.2 * (0.9^0) = 0.3333 + 0.24 + 0.2 = 0.7733
    expected_shallow = (0.5 * (2.0 / 3.0)) + (0.3 * 0.8) + (0.2 * 1.0)
    assert pytest.approx(score_shallow) == expected_shallow

