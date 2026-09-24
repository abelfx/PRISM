"""
PRISM Learned A* Search Engine Subsystem.

Provides priority-queue agenda management, cumulative path cost tracking,
heuristic distance estimation, and proof path reconstruction.
"""

from prism.search.backward import (
    BackwardCandidate,
    backward_step,
    check_connection,
    compute_backward_score,
)
from prism.search.bidirectional import (
    BidirectionalSearchEngine,
    stitch_proof_traces,
)
from prism.search.engine import AStarSearchEngine, SearchResult
from prism.search.pln_runtime import apply_pln_pair
from prism.search.rules import (
    ParsedSentence,
    apply_candidate,
    generate_forward_candidates,
    parse_sentence,
)
from prism.search.state import (
    BidirectionalSearchNode,
    BidirectionalSearchResult,
    SearchNode,
    extract_proof_path,
    extract_statement_term,
    hash_belief_state,
    matches_goal,
)

__all__ = [
    "SearchNode",
    "BidirectionalSearchNode",
    "BidirectionalSearchResult",
    "hash_belief_state",
    "matches_goal",
    "extract_statement_term",
    "extract_proof_path",
    "ParsedSentence",
    "parse_sentence",
    "apply_pln_pair",
    "generate_forward_candidates",
    "apply_candidate",
    "AStarSearchEngine",
    "SearchResult",
    "BackwardCandidate",
    "backward_step",
    "check_connection",
    "compute_backward_score",
    "BidirectionalSearchEngine",
    "stitch_proof_traces",
]

