"""
PRISM Learned A* Search Engine Subsystem.

Provides priority-queue agenda management, cumulative path cost tracking,
heuristic distance estimation, and proof path reconstruction.
"""

from prism.search.engine import AStarSearchEngine, SearchResult
from prism.search.rules import (
    ParsedSentence,
    apply_candidate,
    deduce_pair,
    generate_forward_candidates,
    parse_sentence,
)
from prism.search.state import (
    SearchNode,
    extract_proof_path,
    extract_statement_term,
    hash_belief_state,
    matches_goal,
)

__all__ = [
    "SearchNode",
    "hash_belief_state",
    "matches_goal",
    "extract_statement_term",
    "extract_proof_path",
    "ParsedSentence",
    "parse_sentence",
    "deduce_pair",
    "generate_forward_candidates",
    "apply_candidate",
    "AStarSearchEngine",
    "SearchResult",
]
