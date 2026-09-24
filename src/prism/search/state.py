"""
State Representation and Search Node Abstractions for PRISM A* Engine.

Defines the search tree node, priority queue evaluation ordering, canonical
belief state hashing for closed-set duplicate detection, and proof path reconstruction.
"""

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Dict, List, Optional, Sequence, Set


@dataclass
class SearchNode:
    """
    Representation of a discrete state node in the PRISM A* search space.

    Attributes
    ----------
    state_id : int
        Monotonically increasing unique identifier for this node.
    tasks : List[Any]
        Active derivation tasks pending evaluation.
    beliefs : List[Any]
        Accumulated belief buffer (axioms + derived lemmas).
    g_cost : float
        Cumulative path cost from root to current node.
    h_cost : float
        Heuristic distance estimate to goal (inverted Tier 1 score).
    f_cost : float
        Evaluation function score f(n) = g(n) + h(n).
    depth : int
        Derivation depth of the current state.
    parent_id : Optional[int]
        state_id of the parent node (None for initial root state).
    action : Optional[Any]
        The candidate sentence or deduction rule applied to produce this node.
    step_created : int
        Search engine iteration step at which this node was generated.
    """

    state_id: int
    tasks: List[Any]
    beliefs: List[Any]
    g_cost: float
    h_cost: float
    f_cost: float
    depth: int
    parent_id: Optional[int] = None
    action: Optional[Any] = None
    step_created: int = 0

    def __lt__(self, other: "SearchNode") -> bool:
        """
        Priority queue comparison for min-heap.
        Orders by f_cost ascending; breaks ties with h_cost ascending,
        then deterministically by state_id.
        """
        if abs(self.f_cost - other.f_cost) > 1e-9:
            return self.f_cost < other.f_cost
        if abs(self.h_cost - other.h_cost) > 1e-9:
            return self.h_cost < other.h_cost
        return self.state_id < other.state_id


def extract_statement_term(sentence: Any) -> str:
    """
    Extract canonical string representation of a sentence's relational statement.

    Inputs:
        sentence (Any): Sentence S-expression (list or string).

    Outputs:
        str: Relational term, e.g. '(Inheritance A B)'.

    What it does NOT handle:
        Does not evaluate truth values or validate logic syntax.
    """
    if isinstance(sentence, (list, tuple)) and len(sentence) >= 2:
        body = sentence[1]
        if isinstance(body, (list, tuple)) and len(body) >= 1:
            term = body[0]
            if isinstance(term, (list, tuple)):
                return "(" + " ".join(str(x) for x in term) + ")"
            return str(term)
        return str(body)

    sent_str = str(sentence).strip()
    match = re.search(r"\(Sentence\s+\(\(?(.+?)\)?\s+\(stv", sent_str)
    if match:
        extracted = match.group(1).strip()
        while extracted.startswith("(") and extracted.endswith(")"):
            extracted = extracted[1:-1].strip()
        return "(" + extracted + ")"
    return sent_str


def hash_belief_state(beliefs: Sequence[Any]) -> str:
    """
    Compute a deterministic canonical hash string for a collection of beliefs.

    Permutation invariant: two states with the identical set of relational
    beliefs in different order will produce the exact same hash.

    Inputs:
        beliefs (Sequence[Any]): Collection of belief sentences.

    Outputs:
        str: Hexadecimal SHA-256 hash digest.

    What it does NOT handle:
        Does not evaluate truth value equivalence or perform semantic subsumption.
    """
    canonical_terms: List[str] = sorted(extract_statement_term(b) for b in beliefs)
    serialized = "|".join(canonical_terms)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def normalize_term_str(term: Any) -> str:
    """Normalize whitespace and all outermost parentheses for string comparison."""
    s = str(term).strip()
    s = re.sub(r"\s+", " ", s)
    while s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    return s


def matches_goal(sentence: Any, goal: Any) -> bool:
    """
    Determine whether a sentence satisfies the target search goal.

    Inputs:
        sentence (Any): Candidate sentence (S-expression list or string).
        goal (Any): Target query goal term (e.g. ['Inheritance', 'A', 'Z'] or '(Inheritance A Z)').

    Outputs:
        bool: True if relational terms match.

    What it does NOT handle:
        Does not check truth value thresholds or confidence requirements.
    """
    if sentence is None or goal is None:
        return False

    term_str = normalize_term_str(extract_statement_term(sentence))
    goal_term = (
        extract_statement_term(goal)
        if (isinstance(goal, (list, tuple)) and len(goal) >= 2 and goal[0] == "Sentence")
        else goal
    )

    if isinstance(goal_term, (list, tuple)):
        goal_str = normalize_term_str(" ".join(str(x) for x in goal_term))
    else:
        goal_str = normalize_term_str(str(goal_term))

    return term_str == goal_str


def extract_proof_path(
    final_node: SearchNode,
    node_registry: Dict[int, SearchNode],
) -> List[SearchNode]:
    """
    Backtrack from the goal node to root to reconstruct the complete derivation path.

    Inputs:
        final_node (SearchNode): Node where goal was satisfied.
        node_registry (Dict[int, SearchNode]): Map of state_id -> SearchNode.

    Outputs:
        List[SearchNode]: Chronological list of nodes from initial state to goal node.

    What it does NOT handle:
        Does not verify validity of intermediate inference rules.
    """
    path: List[SearchNode] = []
    curr: Optional[SearchNode] = final_node

    while curr is not None:
        path.append(curr)
        if curr.parent_id is None:
            break
        curr = node_registry.get(curr.parent_id)

    path.reverse()
    return path


@dataclass
class BidirectionalSearchNode:
    """
    Search node for dual-frontier bidirectional A* search.

    Attributes
    ----------
    state_id : int
        Monotonically increasing state ID.
    direction : str
        Search direction: "FORWARD" or "BACKWARD".
    node : SearchNode
        Underlying SearchNode instance tracking tasks, beliefs, costs.
    subgoals : List[Any]
        Active required subgoals (used primarily in backward search).
    """

    state_id: int
    direction: str
    node: SearchNode
    subgoals: List[Any] = field(default_factory=list)

    def __lt__(self, other: "BidirectionalSearchNode") -> bool:
        """Priority ordering delegated to inner SearchNode."""
        return self.node < other.node


@dataclass
class BidirectionalSearchResult:
    """
    Result container for bidirectional search execution.

    Attributes
    ----------
    goal_found : bool
        Whether the derivation successfully reached the target goal.
    meeting_point : Optional[Any]
        The intermediate bridging lemma where forward and backward frontiers met.
    proof_path : List[SearchNode]
        Reconstructed sequence of forward-executable states.
    goal_sentence : Optional[Any]
        The exact derived goal sentence.
    steps_expanded : int
        Total derivation steps expanded across both frontiers.
    forward_steps : int
        Steps expanded along the forward frontier.
    backward_steps : int
        Steps expanded along the backward frontier.
    nodes_generated : int
        Total number of state nodes generated.
    visited_states_count : int
        Total number of unique states in closed sets.
    wall_clock_seconds : float
        Elapsed search time in seconds.
    stalled : bool
        Whether search stalled before recovery or termination.
    proof_trace : List[Any]
        Chronological proof trace steps if tracing was enabled.
    subgoals_proposed : List[Any]
        Subgoals proposed during search by Tier 2 reasoner.
    """

    goal_found: bool
    meeting_point: Optional[Any]
    proof_path: List[SearchNode]
    goal_sentence: Optional[Any]
    steps_expanded: int
    forward_steps: int
    backward_steps: int
    nodes_generated: int
    visited_states_count: int
    wall_clock_seconds: float
    stalled: bool = False
    proof_trace: List[Any] = field(default_factory=list)
    subgoals_proposed: List[Any] = field(default_factory=list)

