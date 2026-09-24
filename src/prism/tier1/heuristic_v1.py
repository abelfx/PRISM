"""
PRISM Tier 1 v1 Symbolic Heuristic Scorer.

Computes candidate sentence priority scores relative to a derivation goal using
structural atom overlap, expected truth-value confidence, and a geometric
discount on derivation depth.

Formula (§5.1):
    score_v1(candidate, goal) = alpha * overlap(S, G) + beta * confidence + delta * (gamma ^ depth)
"""

import re
from typing import Any, Set
from prism.core.config import DEFAULT_CONFIG, Tier1Config


def extract_atoms(expr: Any) -> Set[str]:
    """
    Extract atomic symbolic tokens from a MeTTa expression or Python term.

    Inputs:
        expr (Any): Nested list, tuple, or string representation of a MeTTa term.

    Outputs:
        Set[str]: Set of identifier tokens, excluding numbers and structural keywords.

    What it does NOT handle:
        Does not perform semantic analysis, type-checking, or logic variable unification.
    """
    if isinstance(expr, (int, float)):
        return set()
    if isinstance(expr, str):
        tokens = re.findall(r"[A-Za-z0-9_\-]+", expr)
        return {
            t
            for t in tokens
            if not re.match(r"^-?\d+(\.\d+)?$", t)
            and t not in {"Sentence", "stv", "Concept", "Predicate", "List"}
        }
    if isinstance(expr, (list, tuple)):
        atoms: Set[str] = set()
        for sub in expr:
            atoms |= extract_atoms(sub)
        return atoms
    return set()


def extract_confidence(sentence: Any, default_confidence: float) -> float:
    """
    Extract truth-value confidence from a Sentence structure.

    Inputs:
        sentence (Any): Sentence representation (list, tuple, or string).
        default_confidence (float): Value to return if extraction fails.

    Outputs:
        float: Confidence in range [0.0, 1.0].

    What it does NOT handle:
        Does not compute truth value revisions or evaluate evidence stamps.
    """
    try:
        if isinstance(sentence, (list, tuple)) and len(sentence) >= 2:
            body = sentence[1]
            if isinstance(body, (list, tuple)) and len(body) >= 2:
                tv = body[1]
                if isinstance(tv, (list, tuple)) and len(tv) >= 3:
                    return float(tv[2])
        text = str(sentence)
        match = re.search(r"stv\s+[\d\.\-eE]+\s+([\d\.\-eE]+)", text)
        if match:
            return float(match.group(1))
    except (ValueError, IndexError, TypeError):
        pass
    return default_confidence


def extract_depth(sentence: Any) -> int:
    """
    Extract derivation depth from the sentence evidence stamp.

    Inputs:
        sentence (Any): Sentence representation [Sentence, body, stamp].

    Outputs:
        int: Derivation depth (0 for base premise, 1 for 1 deduction step, etc.).

    What it does NOT handle:
        Does not check stamp disjointness or validate evidence consistency.
    """
    try:
        if isinstance(sentence, (list, tuple)) and len(sentence) >= 3:
            stamp = sentence[2]
            if isinstance(stamp, (list, tuple)):
                # Base fact has 1 premise index -> depth 0. Two premises resolved -> length 2 -> depth 1.
                return max(0, len(stamp) - 1)
    except (TypeError, IndexError):
        pass
    return 0


def compute_overlap(sentence_atoms: Set[str], goal_atoms: Set[str]) -> float:
    """
    Compute Jaccard-style atom overlap between sentence atoms and goal atoms.

    Inputs:
        sentence_atoms (Set[str]): Atoms in the candidate sentence.
        goal_atoms (Set[str]): Atoms in the goal query.

    Outputs:
        float: Overlap score in [0.0, 1.0].

    What it does NOT handle:
        Does not account for predicate semantics or relational directionality.
    """
    if not goal_atoms:
        return 0.0
    return len(sentence_atoms & goal_atoms) / len(goal_atoms)


def compute_depth_discount(depth: int, delta: float, gamma: float) -> float:
    """
    Compute geometric depth discount bonus for derivation depth.

    Inputs:
        depth (int): Derivation depth (>= 0).
        delta (float): Weight for depth bonus.
        gamma (float): Geometric decay factor (0.0 to 1.0).

    Outputs:
        float: Discounted depth bonus delta * (gamma ^ depth).

    What it does NOT handle:
        Does not enforce step budgets or cut off derivations.
    """
    effective_depth = max(0, depth)
    return delta * (gamma ** effective_depth)


def compute_v1_score(
    sentence: Any,
    goal: Any,
    config: Tier1Config = DEFAULT_CONFIG.tier1,
) -> float:
    """
    Compute composite Tier 1 v1 score combining overlap, confidence, and depth discount.

    Inputs:
        sentence (Any): Candidate Sentence representation.
        goal (Any): Goal query representation.
        config (Tier1Config): Configuration parameters (alpha, beta, delta, gamma, default_confidence).

    Outputs:
        float: Calculated priority score.

    What it does NOT handle:
        Does not perform score caching, does not handle MeTTa/FFI exceptions,
        and does not perform queue management.
    """
    s_atoms = extract_atoms(sentence)
    g_atoms = extract_atoms(goal)
    conf = extract_confidence(sentence, config.default_confidence)
    depth = extract_depth(sentence)

    overlap = compute_overlap(s_atoms, g_atoms)
    depth_bonus = compute_depth_discount(depth, config.delta, config.gamma)

    return (config.alpha * overlap) + (config.beta * conf) + depth_bonus
