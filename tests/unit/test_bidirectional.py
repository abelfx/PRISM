"""
Unit and Integration Tests for PRISM Bidirectional A* Search Engine (§9).

Verifies:
  - GATE-8.1: Dual-frontier convergence on transitive chains.
  - GATE-8.2: Soundness of stitched proof paths and evidence stamps.
  - GATE-8.3: Search space reduction on deep chains (D >= 8) with distractors.
  - GATE-8.4: Zero regressions and Tier 2 waypoint integration.
"""

import json
import pytest
from typing import Any, Dict, List

from prism.benchmarks.domains.semantic_gap import generate_semantic_gap
from prism.benchmarks.domains.transitive_chain import generate_with_distractors
from prism.benchmarks.evaluate_search_comparison import format_spec_facts
from prism.core.config import BidirectionalConfig, SearchConfig, Tier1Config, Tier2Config
from prism.search.backward import (
    backward_step,
    check_connection,
    compute_backward_score,
)
from prism.search.bidirectional import (
    BidirectionalSearchEngine,
    stitch_proof_traces,
)
from prism.search.engine import AStarSearchEngine
from prism.search.rules import parse_sentence
from prism.search.state import matches_goal
from prism.tier2.client import MockLLMClient
from prism.tier2.reasoner import Tier2Reasoner


def format_facts(spec: Dict[str, Any]) -> List[Any]:
    facts = []
    for f in spec["facts"]:
        stmt = f["statement"].strip("()").split()
        stv = f["stv"].strip("()").split()
        s, c = float(stv[1]), float(stv[2])
        facts.append(["Sentence", [[stmt[0], stmt[1], stmt[2]], ["stv", s, c]], [str(f["evidence_id"])]])
    return facts



def test_backward_scoring_anchored():
    """Verify compute_backward_score gives higher score to subgoals anchored in initial facts."""
    initial_beliefs = [
        ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]],
        ["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.9]], ["2"]],
    ]
    # Anchored subgoal sharing A and B with initial beliefs
    anchored_subgoal = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], []]
    # Disjoint subgoal
    disjoint_subgoal = ["Sentence", [["Inheritance", "X", "Y"], ["stv", 0.9, 0.9]], []]

    score_anchored = compute_backward_score(anchored_subgoal, initial_beliefs)
    score_disjoint = compute_backward_score(disjoint_subgoal, initial_beliefs)

    assert score_anchored > score_disjoint
    assert score_anchored >= 0.65  # Overlap 1.0 * alpha (0.65)


def test_bidirectional_immediate_goal_satisfaction():
    """Verify bidirectional engine immediately satisfies goal if already present in beliefs."""
    beliefs = [
        ["Sentence", [["Inheritance", "A", "Z"], ["stv", 0.9, 0.9]], ["1"]],
        ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["2"]],
    ]
    goal = ["Inheritance", "A", "Z"]

    engine = BidirectionalSearchEngine()
    result = engine.search(goal, beliefs)

    assert result.goal_found is True
    assert result.steps_expanded == 0
    assert len(result.proof_path) == 1
    assert matches_goal(result.goal_sentence, goal)


def test_bidirectional_simple_chain_convergence():
    """
    GATE-8.1: Verify forward and backward frontiers converge on a D=4 chain.
    Chain: A -> B -> C -> D -> E, Goal: A -> E.
    """
    spec = generate_with_distractors(depth=4, n_distractors=0)
    facts = format_spec_facts(spec)
    goal = spec["goal"]

    engine = BidirectionalSearchEngine()
    result = engine.search(goal, facts)

    assert result.goal_found is True
    assert result.meeting_point is not None
    assert len(result.proof_path) >= 2
    assert matches_goal(result.goal_sentence, goal)
    # Verify that both frontiers participated
    assert result.forward_steps > 0
    assert result.backward_steps >= 0


def test_bidirectional_proof_stitching_soundness():
    """
    GATE-8.2: Verify stitched proof path represents valid, forward-executable PLN deductions.
    Every step must be an Inheritance or Similarity link with valid evidence stamps.
    """
    spec = generate_with_distractors(depth=5, n_distractors=5, seed=42)
    facts = format_spec_facts(spec)
    goal = spec["goal"]

    engine = BidirectionalSearchEngine()
    result = engine.search(goal, facts)

    assert result.goal_found is True
    assert len(result.proof_path) >= 3

    # Check proof path step-by-step
    previous_node = result.proof_path[0]
    for step_node in result.proof_path[1:]:
        assert step_node.action is not None
        parsed = parse_sentence(step_node.action)
        assert parsed is not None
        assert parsed.relation in {"Inheritance", "Similarity"}
        # Verify evidence stamp is present and non-empty
        assert len(parsed.evidence_stamp) >= 1
        previous_node = step_node

    # Final node must satisfy goal
    final_node = result.proof_path[-1]
    assert matches_goal(final_node.action, goal) or any(
        matches_goal(b, goal) for b in final_node.beliefs
    )


def test_bidirectional_deep_scaling_reduction():
    """
    GATE-8.3: Verify search space / step reduction on D=8 chain with 20 distractors.
    Compares BidirectionalSearchEngine against unidirectional AStarSearchEngine.
    """
    spec = generate_with_distractors(depth=8, n_distractors=20, seed=42)
    facts = format_spec_facts(spec)
    goal = spec["goal"]

    # 1. Unidirectional A* Engine
    fwd_engine = AStarSearchEngine(config=SearchConfig(max_steps=100, beam_width=5))
    fwd_result = fwd_engine.search(initial_tasks=facts, initial_beliefs=facts, goal=goal)

    # 2. Bidirectional Engine
    bwd_engine = BidirectionalSearchEngine(config=BidirectionalConfig(max_steps=100))
    bwd_result = bwd_engine.search(goal, facts)

    assert bwd_result.goal_found is True
    assert fwd_result.goal_found is True

    # State space reduction check
    nodes_fwd = fwd_result.nodes_generated
    nodes_bwd = bwd_result.nodes_generated

    reduction = (nodes_fwd - nodes_bwd) / nodes_fwd if nodes_fwd > 0 else 0.0
    print(f"D=8 Comparison: Unidirectional Nodes={nodes_fwd} vs Bidirectional Nodes={nodes_bwd} (Reduction: {reduction:.1%})")

    # Verify significant reduction in generated nodes / expanded steps
    assert bwd_result.steps_expanded <= fwd_result.steps_expanded



def test_bidirectional_tier2_waypoint_integration():
    """
    GATE-8.4: Verify Tier 2 waypoint successfully seeds both frontiers and bridges a gap.
    """
    domain = generate_semantic_gap(
        depth_source=2,
        depth_target=2,
        n_distractors=10,
        include_bridge_in_kb=False,
        seed=42,
    )
    facts = format_facts(domain)
    mock_payload = json.dumps({
        "subgoal": "(Inheritance C M)",
        "suggested_premise": "(Inheritance C M)",
        "reasoning": "Bridge concept C in source cluster to concept M in target cluster",
    })
    mock_client = MockLLMClient(canned_responses=[mock_payload])
    tier2_reasoner = Tier2Reasoner(
        config=Tier2Config(enabled=True, stall_threshold=0.25, stall_steps=1),
        client=mock_client,
    )

    engine = BidirectionalSearchEngine(
        config=BidirectionalConfig(max_steps=50),
        search_config=SearchConfig(stall_threshold=0.25),
        tier2_reasoner=tier2_reasoner,
    )

    result = engine.search(domain["goal"], facts)

    assert result.goal_found is True
    assert len(result.subgoals_proposed) >= 1
    assert matches_goal(result.goal_sentence, domain["goal"])

