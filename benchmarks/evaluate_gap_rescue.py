"""
Semantic Gap Stall & Recovery Benchmark for PRISM Tier 2.

Evaluates how Tier 2 strategic subgoal reasoning resolves reasoning stalls
over semantic gaps where local symbolic heuristics (Tier 1) have zero guidance.

Usage:
  python3 -m prism.benchmarks.evaluate_gap_rescue         # Offline mock mode (fast)
  python3 -m prism.benchmarks.evaluate_gap_rescue --live  # Live OpenRouter mode
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

from prism.benchmarks.domains.semantic_gap import generate_semantic_gap
from prism.core.config import SearchConfig, Tier2Config
from prism.search.engine import AStarSearchEngine
from prism.tier2.client import MockLLMClient, OpenRouterClient
from prism.tier2.reasoner import Tier2Reasoner


def format_facts(spec: Dict[str, Any]) -> List[Any]:
    facts = []
    for f in spec["facts"]:
        stmt = f["statement"].strip("()").split()
        stv = f["stv"].strip("()").split()
        s, c = float(stv[1]), float(stv[2])
        facts.append(["Sentence", [[stmt[0], stmt[1], stmt[2]], ["stv", s, c]], [str(f["evidence_id"])]])
    return facts


def run_gap_benchmark(live: bool = False):
    print("=" * 95)
    mode_str = "LIVE OPENROUTER" if live else "OFFLINE MOCK"
    print(f"PRISM TIER 2: SEMANTIC GAP STALL & RESCUE BENCHMARK ({mode_str})")
    print("=" * 95)

    spec = generate_semantic_gap(
        depth_source=2,
        depth_target=2,
        n_distractors=10,
        include_bridge_in_kb=False,
        seed=42,
    )
    facts = format_facts(spec)
    goal = spec["goal"]

    print(f"\nScenario: Semantic Gap Benchmark (Source: A->B->C, Target: M->N->Z)")
    print(f"Goal: {goal} | Initial Facts: {len(facts)} | Distractors: {len(spec['distractor_facts'])}")
    print(f"Missing Link: Semantic bridge required between C and target cluster")
    print("-" * 95)
    print(f"{'Search Configuration':<28} | {'Success':<7} | {'Steps':<7} | {'Subgoals':<9} | {'Proof Len':<9} | {'Time (s)':<9}")
    print("-" * 95)

    # 1. Pure Forward A* (No Tier 2)
    cfg_unassisted = SearchConfig(max_steps=50, guided=True, enable_tier2=False, stall_threshold=0.25)
    eng_unassisted = AStarSearchEngine(config=cfg_unassisted)
    t0 = time.perf_counter()
    res_unassisted = eng_unassisted.search(initial_tasks=facts, initial_beliefs=facts, goal=goal)
    t_unassisted = time.perf_counter() - t0

    status_unassisted = "PASS" if res_unassisted.goal_found else "FAIL"
    print(f"{'A* Search (Unassisted)':<28} | {status_unassisted:<7} | {res_unassisted.steps_expanded:<7} | {len(res_unassisted.subgoals_proposed):<9} | {len(res_unassisted.proof_path):<9} | {t_unassisted:.4f}s")

    # 2. Tier 2 Guided A* (Strategic Subgoal Reasoning)
    if live:
        t2_cfg = Tier2Config(
            backend="openrouter",
            model_name="nex-agi/nex-n2.5-mini:free",
            stall_threshold=0.25,
            stall_steps=1,
            timeout_seconds=30.0,
            max_tokens=1500,
        )
        client = OpenRouterClient(t2_cfg)
        label = "Tier 2 Guided (OpenRouter Live)"
    else:
        canned_subgoal = json.dumps({
            "subgoal": "(Inheritance C M)",
            "suggested_premise": "(Inheritance C M)",
            "reasoning": "Bridge concept C in source cluster to concept M in target cluster",
        })
        client = MockLLMClient(canned_responses=[canned_subgoal])
        t2_cfg = Tier2Config(stall_threshold=0.25, stall_steps=1)
        label = "Tier 2 Guided (Mock Rescued)"

    reasoner = Tier2Reasoner(config=t2_cfg, client=client)
    cfg_assisted = SearchConfig(max_steps=50, guided=True, enable_tier2=True, stall_threshold=0.25)
    eng_assisted = AStarSearchEngine(config=cfg_assisted, tier2_reasoner=reasoner)
    t0 = time.perf_counter()
    res_assisted = eng_assisted.search(initial_tasks=facts, initial_beliefs=facts, goal=goal)
    t_assisted = time.perf_counter() - t0

    status_assisted = "PASS" if res_assisted.goal_found else "FAIL"
    print(f"{label:<28} | {status_assisted:<7} | {res_assisted.steps_expanded:<7} | {len(res_assisted.subgoals_proposed):<9} | {len(res_assisted.proof_path):<9} | {t_assisted:.4f}s")

    print("-" * 95)
    if res_assisted.subgoals_proposed:
        sg = res_assisted.subgoals_proposed[0]
        print(f"\n[Tier 2 Strategic Intervention Output]")
        print(f"  Proposed Subgoal : {sg.subgoal_str}")
        print(f"  Suggested Premise: {sg.suggested_premise_str}")
        print(f"  Model Rationale  : {sg.reasoning}")

    print("\n" + "=" * 95)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PRISM Tier 2 Semantic Gap Benchmark")
    parser.add_argument("--live", action="store_true", help="Run live against OpenRouter API")
    args = parser.parse_args()
    run_gap_benchmark(live=args.live)
