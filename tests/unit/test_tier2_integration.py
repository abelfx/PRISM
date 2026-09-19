"""
Integration tests for PRISM Tier 2 Strategic LLM Reasoner.
Verifies GATE-7.4: Semantic gap stall detection, subgoal recovery, and error safety.
"""

import json
from typing import Any, Dict, List

from prism.benchmarks.domains.semantic_gap import generate_semantic_gap
from prism.benchmarks.evaluate_search_comparison import format_spec_stvs
from prism.core.config import SearchConfig, Tier2Config
from prism.search.engine import AStarSearchEngine
from prism.tier2.client import MockLLMClient
from prism.tier2.reasoner import Tier2Reasoner


def _format_facts(spec: Dict[str, Any]) -> List[Any]:
    """Helper to convert domain facts into Sentence S-expression lists."""
    facts = []
    for f in spec["facts"]:
        stmt = f["statement"].strip("()").split()
        stv = f["stv"].strip("()").split()
        s, c = float(stv[1]), float(stv[2])
        facts.append(["Sentence", [[stmt[0], stmt[1], stmt[2]], ["stv", s, c]], [str(f["evidence_id"])]])
    return facts


def test_tier2_search_rescue_on_derivable_semantic_gap():
    """GATE-7.4: Tier 2 prioritizes a bridge that PLN can derive from input facts."""
    spec = generate_semantic_gap(
        depth_source=2,
        depth_target=2,
        n_distractors=10,
        include_bridge_in_kb=False,
        include_bridge_support=True,
        seed=42,
    )
    facts = _format_facts(spec)
    stvs = format_spec_stvs(spec)
    goal = spec["goal"]

    cfg_unassisted = SearchConfig(max_steps=50, guided=True, enable_tier2=False)
    eng_unassisted = AStarSearchEngine(config=cfg_unassisted)
    res_unassisted = eng_unassisted.search(
        initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs
    )
    assert res_unassisted.goal_found

    canned_subgoal = json.dumps({
        "subgoal": "(Inheritance C M)",
        "suggested_premise": "(Inheritance C H)",
        "reasoning": "Derive the bridge from known premises C to H and H to M",
    })
    mock_client = MockLLMClient(canned_responses=[canned_subgoal])
    t2_cfg = Tier2Config(stall_threshold=0.80, stall_steps=1, cooldown_steps=100)
    reasoner = Tier2Reasoner(config=t2_cfg, client=mock_client)

    cfg_assisted = SearchConfig(max_steps=50, beam_width=1, guided=True, enable_tier2=True, stall_threshold=0.80)
    eng_assisted = AStarSearchEngine(config=cfg_assisted, tier2_reasoner=reasoner)
    res_assisted = eng_assisted.search(
        initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs
    )

    assert res_assisted.goal_found
    assert len(res_assisted.subgoals_proposed) >= 1
    assert res_assisted.subgoals_proposed[0].subgoal == ["Inheritance", "C", "M"]
    assert len(res_assisted.proof_path) > 0
    assert all("T2_" not in str(getattr(step, "action", "")) for step in res_assisted.proof_path)


def test_tier2_does_not_inject_missing_bridge():
    """A genuinely unsupported LLM bridge remains unproved and cannot satisfy the goal."""
    spec = generate_semantic_gap(
        depth_source=2,
        depth_target=2,
        n_distractors=10,
        include_bridge_in_kb=False,
        include_bridge_support=False,
        seed=42,
    )
    facts = _format_facts(spec)
    stvs = format_spec_stvs(spec)
    payload = json.dumps({
        "subgoal": "(Inheritance C M)",
        "suggested_premise": "(Inheritance C M)",
        "reasoning": "Unsupported bridge",
    })
    reasoner = Tier2Reasoner(
        config=Tier2Config(stall_threshold=0.25, stall_steps=1),
        client=MockLLMClient(canned_responses=[payload]),
    )
    result = AStarSearchEngine(
        config=SearchConfig(max_steps=50, guided=True, enable_tier2=True, stall_threshold=0.25),
        tier2_reasoner=reasoner,
    ).search(facts, facts, spec["goal"], concept_stvs=stvs)

    assert not result.goal_found
    assert len(result.subgoals_proposed) >= 1
    assert all("T2_" not in str(getattr(step, "action", "")) for step in result.proof_path)


def test_tier2_pln_apply_when_bridge_is_in_kb():
    """When the bridge fact is already in the KB, real PLN.Apply completes the proof."""
    spec = generate_semantic_gap(
        depth_source=2,
        depth_target=2,
        n_distractors=10,
        include_bridge_in_kb=True,
        seed=42,
    )
    facts = _format_facts(spec)
    stvs = format_spec_stvs(spec)
    goal = spec["goal"]
    cfg = SearchConfig(max_steps=50, guided=True, enable_tier2=False)
    eng = AStarSearchEngine(config=cfg)
    res = eng.search(initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs)
    assert res.goal_found
    assert res.goal_sentence is not None


def test_tier2_search_clean_chain_no_intervention():
    """Verify GATE-7.1: Tier 2 does NOT intervene on clean derivation paths."""
    from prism.benchmarks.domains.transitive_chain import generate_with_distractors
    from prism.benchmarks.evaluate_search_comparison import format_spec_facts

    spec = generate_with_distractors(depth=4, n_distractors=5, seed=42)
    facts = format_spec_facts(spec)
    stvs = format_spec_stvs(spec)
    goal = spec["goal"]

    mock_client = MockLLMClient()
    t2_cfg = Tier2Config(stall_threshold=0.20, stall_steps=5)
    reasoner = Tier2Reasoner(config=t2_cfg, client=mock_client)

    cfg = SearchConfig(max_steps=50, guided=True, enable_tier2=True)
    eng = AStarSearchEngine(config=cfg, tier2_reasoner=reasoner)
    res = eng.search(initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs)

    assert res.goal_found
    # On clean chain, Tier 2 should have 0 proposals
    assert len(res.subgoals_proposed) == 0
    assert len(mock_client.call_history) == 0


def test_tier2_search_error_containment_during_search():
    """Verify GATE-7.3: Search gracefully finishes without unhandled crashes when LLM fails."""
    spec = generate_semantic_gap(
        depth_source=2,
        depth_target=2,
        n_distractors=5,
        include_bridge_in_kb=False,
        seed=42,
    )
    facts = _format_facts(spec)
    stvs = format_spec_stvs(spec)
    goal = spec["goal"]

    failing_client = MockLLMClient(error_mode=True)
    t2_cfg = Tier2Config(stall_threshold=0.25, stall_steps=1)
    reasoner = Tier2Reasoner(config=t2_cfg, client=failing_client)

    cfg = SearchConfig(max_steps=30, guided=True, enable_tier2=True, stall_threshold=0.25)
    eng = AStarSearchEngine(config=cfg, tier2_reasoner=reasoner)

    # Must complete cleanly without throwing exceptions
    res = eng.search(initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs)
    assert not res.goal_found
    assert len(res.subgoals_proposed) == 0
