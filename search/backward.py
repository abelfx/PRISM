"""
Backward Inference Primitives and Goal Decomposition for PRISM.

Implements backward chaining steps (§9.2) and meet-in-the-middle connection
checks (§9.3) for bidirectional search and Tier 2 LLM subgoal integration.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from prism.search.rules import ParsedSentence, parse_sentence
from prism.search.state import matches_goal


@dataclass(frozen=True)
class BackwardCandidate:
    """
    Hypothesized backward inference rule application decomposed from a subgoal.

    Attributes
    ----------
    subgoal : Any
        Target sentence or term to be established.
    rule_name : str
        Name of the inference rule (e.g., 'Deduction', 'Similarity').
    available_premises : Tuple[Any, ...]
        Premises already confirmed present in the belief space.
    missing_premises : Tuple[Any, ...]
        Required premises not yet proven (these form new subgoals).
    completeness : float
        Ratio of available premises to total required premises in [0.0, 1.0].
    """

    subgoal: Any
    rule_name: str
    available_premises: Tuple[Any, ...]
    missing_premises: Tuple[Any, ...]
    completeness: float = 0.0


def backward_step(
    subgoal: Any,
    beliefs: Sequence[Any],
    rules: Optional[Sequence[str]] = None,
) -> List[BackwardCandidate]:
    """
    Decompose a target subgoal into required premises via backward rule inversion (§9.2).

    For a target `(Inheritance A Z)`, transitive deduction requires:
      Premise 1: `(Inheritance A ?M)`
      Premise 2: `(Inheritance ?M Z)`

    Inspects known beliefs to ground candidate intermediate concepts `?M`.
    If `(Inheritance A M)` is known, `(Inheritance M Z)` becomes a required subgoal.
    If `(Inheritance M Z)` is known, `(Inheritance A M)` becomes a required subgoal.

    Parameters
    ----------
    subgoal : Any
        Target goal term or Sentence.
    beliefs : Sequence[Any]
        Current known beliefs / AtomSpace facts.
    rules : Optional[Sequence[str]]
        Inference rules to consider (defaults to ['Deduction']).

    Returns
    -------
    List[BackwardCandidate]
        List of hypothesized rule decompositions, ranked by completeness.
    """
    target = parse_sentence(subgoal)
    if not target:
        return []

    parsed_beliefs: List[ParsedSentence] = []
    for b in beliefs:
        p = parse_sentence(b)
        if p:
            parsed_beliefs.append(p)

    active_rules = set(rules) if rules else {"Deduction"}
    candidates: List[BackwardCandidate] = []

    if "Deduction" in active_rules and target.relation in {"Inheritance", "Similarity"}:
        sub = target.subject
        obj = target.object_node

        # Index known intermediate connections
        # Forward anchors: (Rel sub ?M)
        forward_anchors: Dict[str, ParsedSentence] = {}
        # Backward anchors: (Rel ?M obj)
        backward_anchors: Dict[str, ParsedSentence] = {}

        for b in parsed_beliefs:
            if b.relation in {"Inheritance", "Similarity"}:
                if b.subject == sub and b.object_node != obj:
                    forward_anchors[b.object_node] = b
                elif b.object_node == obj and b.subject != sub:
                    backward_anchors[b.subject] = b

        all_intermediate_concepts = set(forward_anchors.keys()) | set(backward_anchors.keys())

        for m in sorted(list(all_intermediate_concepts)):
            available = []
            missing = []

            # Check Premise 1: (Inheritance sub m)
            if m in forward_anchors:
                available.append(forward_anchors[m].raw)
            else:
                missing.append(["Sentence", [[target.relation, sub, m], ["stv", 1.0, 0.9]], []])

            # Check Premise 2: (Inheritance m obj)
            if m in backward_anchors:
                available.append(backward_anchors[m].raw)
            else:
                missing.append(["Sentence", [[target.relation, m, obj], ["stv", 1.0, 0.9]], []])

            total_premises = len(available) + len(missing)
            completeness = len(available) / total_premises if total_premises > 0 else 0.0

            candidates.append(
                BackwardCandidate(
                    subgoal=subgoal,
                    rule_name="Deduction",
                    available_premises=tuple(available),
                    missing_premises=tuple(missing),
                    completeness=round(completeness, 4),
                )
            )

    # Sort descending by completeness (highest partially-proven candidates first)
    candidates.sort(key=lambda x: -x.completeness)
    return candidates


def check_connection(
    forward_beliefs: Sequence[Any],
    backward_subgoals: Sequence[Any],
) -> Optional[Tuple[Any, Any]]:
    """
    Check if any forward-derived fact satisfies a backward subgoal (§9.3).

    Enables meet-in-the-middle bidirectional termination.

    Parameters
    ----------
    forward_beliefs : Sequence[Any]
        Beliefs derived from the forward search frontier.
    backward_subgoals : Sequence[Any]
        Target subgoals proposed by backward decomposition or Tier 2 reasoner.

    Returns
    -------
    Optional[Tuple[Any, Any]]
        (satisfying_belief, matched_subgoal) if connection found, else None.
    """
    for belief in forward_beliefs:
        for subgoal in backward_subgoals:
            if matches_goal(belief, subgoal):
                return belief, subgoal
    return None
