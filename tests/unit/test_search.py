"""
Unit tests for PRISM Learned A* Search Engine.
Verifies priority queue ordering, belief state hashing, forward candidate expansion,
goal recognition, proof path reconstruction, and cycle prevention.
"""

import heapq
from prism.core.config import SearchConfig, Tier1Config
from prism.search.engine import AStarSearchEngine, SearchResult
from prism.search.rules import (
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


def test_search_node_min_heap_ordering():
    """GATE-5.1: Verify priority queue orders nodes by f_cost, then h_cost, then state_id."""
    node1 = SearchNode(state_id=1, tasks=[], beliefs=[], g_cost=0.5, h_cost=0.5, f_cost=1.0, depth=1)
    node2 = SearchNode(state_id=2, tasks=[], beliefs=[], g_cost=0.2, h_cost=0.3, f_cost=0.5, depth=1)
    node3 = SearchNode(state_id=3, tasks=[], beliefs=[], g_cost=0.4, h_cost=0.6, f_cost=1.0, depth=1)
    node4 = SearchNode(state_id=4, tasks=[], beliefs=[], g_cost=0.5, h_cost=0.5, f_cost=1.0, depth=1)

    heap = [node1, node2, node3, node4]
    heapq.heapify(heap)

    # Lowest f_cost (0.5) must pop first
    first = heapq.heappop(heap)
    assert first.state_id == 2
    assert first.f_cost == 0.5

    # Among f_cost=1.0, lower h_cost (0.5 vs 0.6) pops before higher h_cost
    # node1 has h=0.5, node4 has h=0.5, node3 has h=0.6
    second = heapq.heappop(heap)
    assert second.state_id in {1, 4}
    assert second.h_cost == 0.5

    third = heapq.heappop(heap)
    assert third.state_id in {1, 4}
    assert third.h_cost == 0.5

    fourth = heapq.heappop(heap)
    assert fourth.state_id == 3
    assert fourth.h_cost == 0.6


def test_belief_state_hashing_invariance():
    """GATE-5.2: Verify hash_belief_state produces identical hash regardless of belief ordering."""
    b1 = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]]
    b2 = ["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.9]], ["2"]]
    b3 = ["Sentence", [["Inheritance", "C", "D"], ["stv", 0.9, 0.9]], ["3"]]

    order1 = [b1, b2, b3]
    order2 = [b3, b1, b2]
    order3 = [b2, b3, b1]

    hash1 = hash_belief_state(order1)
    hash2 = hash_belief_state(order2)
    hash3 = hash_belief_state(order3)

    assert hash1 == hash2 == hash3
    assert len(hash1) == 64  # SHA-256 hex string


def test_matches_goal_representations():
    """Verify matches_goal correctly detects goal satisfaction across formats."""
    goal_list = ["Inheritance", "A", "Z"]
    goal_str = "(Inheritance A Z)"

    sent_list = ["Sentence", [["Inheritance", "A", "Z"], ["stv", 0.8, 0.7]], ["1", "2"]]
    sent_str = "(Sentence ((Inheritance A Z) (stv 0.8 0.7)) (1 2))"
    non_matching = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]]

    assert matches_goal(sent_list, goal_list) is True
    assert matches_goal(sent_str, goal_list) is True
    assert matches_goal(sent_list, goal_str) is True
    assert matches_goal(sent_str, goal_str) is True
    assert matches_goal(non_matching, goal_list) is False
    assert matches_goal(None, goal_list) is False


def test_pln_forward_deduction_rule():
    """Verify deduce_pair computes valid conclusions with disjoint stamps."""
    p1 = parse_sentence(["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.8]], ["1"]])
    p2 = parse_sentence(["Sentence", [["Inheritance", "B", "C"], ["stv", 0.8, 0.7]], ["2"]])

    assert p1 is not None and p2 is not None
    conclusion = deduce_pair(p1, p2)
    assert conclusion is not None

    parsed_conc = parse_sentence(conclusion)
    assert parsed_conc is not None
    assert parsed_conc.subject == "A"
    assert parsed_conc.object_node == "C"
    assert parsed_conc.evidence_stamp == ("1", "2")
    assert parsed_conc.strength == round(0.9 * 0.8, 4)
    assert parsed_conc.confidence == round(0.8 * 0.7 * 0.9, 4)

    # Circular evidence check: overlapping stamps must NOT deduce
    p_circ = parse_sentence(["Sentence", [["Inheritance", "C", "D"], ["stv", 0.9, 0.9]], ["1"]])
    assert deduce_pair(p1, p_circ) is None


def test_astar_search_linear_chain_success():
    """GATE-5.3 & GATE-5.4: Test A* search deriving (Inheritance A D) on a 3-step chain."""
    f1 = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]]
    f2 = ["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.9]], ["2"]]
    f3 = ["Sentence", [["Inheritance", "C", "D"], ["stv", 0.9, 0.9]], ["3"]]

    initial_facts = [f1, f2, f3]
    goal = ["Inheritance", "A", "D"]

    engine = AStarSearchEngine()
    result = engine.search(initial_tasks=initial_facts, initial_beliefs=initial_facts, goal=goal)

    assert result.goal_found is True
    assert result.final_node is not None
    assert result.goal_sentence is not None
    assert matches_goal(result.goal_sentence, goal) is True

    # Check proof path reconstruction: root -> step 1 -> goal node
    path = result.proof_path
    assert len(path) >= 2
    assert path[0].parent_id is None
    assert path[-1].state_id == result.final_node.state_id

    # Verify cumulative g_cost increased along the derivation path
    assert path[-1].g_cost > path[0].g_cost
    assert result.steps_expanded > 0


def test_astar_search_cycle_pruning():
    """GATE-5.2: Verify closed-set hashing prevents infinite cycling on symmetric facts."""
    # Symmetrical similarity facts: A <-> B
    s1 = ["Sentence", [["Similarity", "A", "B"], ["stv", 0.9, 0.9]], ["1"]]
    s2 = ["Sentence", [["Similarity", "B", "A"], ["stv", 0.9, 0.9]], ["2"]]

    initial_facts = [s1, s2]
    # Unreachable goal
    goal = ["Inheritance", "X", "Y"]

    config = SearchConfig(max_steps=20, deduplicate_beliefs=True)
    engine = AStarSearchEngine(config=config)
    result = engine.search(initial_tasks=initial_facts, initial_beliefs=initial_facts, goal=goal)

    assert result.goal_found is False
    # Cycle prevention should exhaust the open queue well before max_steps
    assert result.steps_expanded < 20


def test_astar_search_budget_exhaustion():
    """Verify search cleanly terminates when step budget is exhausted."""
    f1 = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]]
    f2 = ["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.9]], ["2"]]

    config = SearchConfig(max_steps=1)
    engine = AStarSearchEngine(config=config)
    result = engine.search(initial_tasks=[f1, f2], initial_beliefs=[f1, f2], goal=["Inheritance", "A", "Z"])

    assert result.goal_found is False
    assert result.steps_expanded == 1


def test_astar_search_diamond_shortcut_preference():
    """GATE-5.4: Test A* on diamond domain prioritizes shortcut over long path."""
    # Shortcut path: A -> S1 -> Z (depth 2)
    s1 = ["Sentence", [["Inheritance", "A", "S1"], ["stv", 0.9, 0.9]], ["1"]]
    s2 = ["Sentence", [["Inheritance", "S1", "Z"], ["stv", 0.9, 0.9]], ["2"]]

    # Long path: A -> L1 -> L2 -> L3 -> Z (depth 4)
    l1 = ["Sentence", [["Inheritance", "A", "L1"], ["stv", 0.9, 0.9]], ["3"]]
    l2 = ["Sentence", [["Inheritance", "L1", "L2"], ["stv", 0.9, 0.9]], ["4"]]
    l3 = ["Sentence", [["Inheritance", "L2", "L3"], ["stv", 0.9, 0.9]], ["5"]]
    l4 = ["Sentence", [["Inheritance", "L3", "Z"], ["stv", 0.9, 0.9]], ["6"]]

    # Distractor fact
    d1 = ["Sentence", [["Inheritance", "D1", "D2"], ["stv", 0.9, 0.9]], ["7"]]

    initial_facts = [s1, s2, l1, l2, l3, l4, d1]
    goal = ["Inheritance", "A", "Z"]

    engine = AStarSearchEngine()
    result = engine.search(initial_tasks=initial_facts, initial_beliefs=initial_facts, goal=goal)

    assert result.goal_found is True
    # The derived goal should have the shortcut evidence stamp ('1', '2')
    parsed_goal = parse_sentence(result.goal_sentence)
    assert parsed_goal is not None
    assert set(parsed_goal.evidence_stamp).issubset({"1", "2"})


def test_astar_search_with_trace_logging():
    """GATE-5.5: Test A* search streaming and retroactively attributing traces."""
    from prism.benchmarks.utils.trace_logger import ProofTraceSession

    f1 = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]]
    f2 = ["Sentence", [["Inheritance", "B", "Z"], ["stv", 0.9, 0.9]], ["2"]]
    d1 = ["Sentence", [["Inheritance", "D1", "D2"], ["stv", 0.9, 0.9]], ["3"]]
    d2 = ["Sentence", [["Inheritance", "D2", "D3"], ["stv", 0.9, 0.9]], ["4"]]

    initial_facts = [f1, f2, d1, d2]
    goal = ["Inheritance", "A", "Z"]

    session = ProofTraceSession(domain_name="test_astar_trace", goal_expr=goal)
    engine = AStarSearchEngine()
    result = engine.search(
        initial_tasks=initial_facts,
        initial_beliefs=initial_facts,
        goal=goal,
        trace_session=session,
    )

    assert result.goal_found is True
    assert len(result.proof_trace) > 0

    # Ensure traces have retroactive proof path attribution
    on_path_traces = [t for t in result.proof_trace if t.on_proof_path is True]
    assert len(on_path_traces) >= 1
    # On-path trace statement should involve on-path concepts
    assert any("A" in t.statement or "Z" in t.statement for t in on_path_traces)


def test_astar_search_stall_detection():
    """Verify stall flag is set when candidate scores fall below stall_threshold."""
    # Isolated facts with zero overlap with goal
    f1 = ["Sentence", [["Inheritance", "X1", "X2"], ["stv", 0.1, 0.1]], ["1"]]
    f2 = ["Sentence", [["Inheritance", "X2", "X3"], ["stv", 0.1, 0.1]], ["2"]]

    goal = ["Inheritance", "A", "Z"]
    config = SearchConfig(max_steps=5, stall_threshold=0.99)  # High threshold triggers stall
    engine = AStarSearchEngine(config=config)
    result = engine.search(initial_tasks=[f1, f2], initial_beliefs=[f1, f2], goal=goal)

    assert result.stalled is True

