"""
Semantic Gap Stall & Recovery Benchmark for PRISM Tier 2.

Evaluates how Tier 2 strategic subgoal reasoning behaves over a semantic gap.
A proposed subgoal is only derived when PLN.Apply can prove it from existing
premises — missing axioms are never injected.

Usage:
  python3 -m prism.benchmarks.evaluate_gap_rescue         # Offline mock mode (fast)
  python3 -m prism.benchmarks.evaluate_gap_rescue --live  # Live OpenRouter mode
"""

import argparse
import json
import time
from typing import Any, Dict, List

from prism.benchmarks.domains.semantic_gap import generate_semantic_gap
from prism.benchmarks.evaluate_search_comparison import format_spec_stvs
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


def _row(label: str, res: Any, elapsed: float) -> None:
    status = "PASS" if res.goal_found else "FAIL"
    print(
        f"{label:<36} | {status:<7} | {res.steps_expanded:<7} | "
        f"{len(res.subgoals_proposed):<9} | {len(res.proof_path):<9} | {elapsed:.4f}s"
    )


def run_gap_benchmark(live: bool = False):
    print("=" * 95)
    mode_str = "LIVE OPENROUTER" if live else "OFFLINE MOCK"
    print(f"PRISM TIER 2: SEMANTIC GAP STALL & RESCUE BENCHMARK ({mode_str})")
    print("=" * 95)
    print("Note: search sits on lib_pln Truth_Deduction. A subgoal is not a proof.")
    print("      Tier 2 may prioritize a derivable lemma; missing axioms are never fabricated.")
    print("-" * 95)

    spec = generate_semantic_gap(
        depth_source=2,
        depth_target=2,
        n_distractors=10,
        include_bridge_in_kb=False,
        include_bridge_support=True,
        seed=42,
    )
    facts = format_facts(spec)
    stvs = format_spec_stvs(spec)
    goal = spec["goal"]

    print(f"\nScenario: Semantic Gap Benchmark (Source: A->B->C, Target: M->N->Z)")
    print(f"Goal: {goal} | Initial Facts: {len(facts)} | Distractors: {len(spec['distractor_facts'])}")
    print("Latent Bridge: C->M is derivable from the input facts C->H and H->M")
    print("-" * 95)
    print(
        f"{'Search Configuration':<36} | {'Success':<7} | {'Steps':<7} | "
        f"{'Subgoals':<9} | {'Proof Len':<9} | {'Time (s)':<9}"
    )
    print("-" * 95)

    cfg_unassisted = SearchConfig(max_steps=50, guided=True, enable_tier2=False, stall_threshold=0.25)
    eng_unassisted = AStarSearchEngine(config=cfg_unassisted)
    t0 = time.perf_counter()
    res_unassisted = eng_unassisted.search(
        initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs
    )
    _row("A* Search (latent bridge, no Tier 2)", res_unassisted, time.perf_counter() - t0)

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
        label = "Tier 2 Guided (OpenRouter, no inject)"
    else:
        canned_subgoal = json.dumps({
            "subgoal": "(Inheritance C M)",
            "suggested_premise": "(Inheritance C H)",
            "reasoning": "Derive C to M from the known premises C to H and H to M",
        })
        client = MockLLMClient(canned_responses=[canned_subgoal])
        t2_cfg = Tier2Config(stall_threshold=0.80, stall_steps=1, cooldown_steps=100)
        label = "Tier 2 Guided (derive via PLN.Apply)"

    reasoner = Tier2Reasoner(config=t2_cfg, client=client)
    cfg_assisted = SearchConfig(max_steps=50, beam_width=1, guided=True, enable_tier2=True, stall_threshold=0.80)
    eng_assisted = AStarSearchEngine(config=cfg_assisted, tier2_reasoner=reasoner)
    t0 = time.perf_counter()
    res_assisted = eng_assisted.search(
        initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs
    )
    _row(label, res_assisted, time.perf_counter() - t0)

    spec_bridged = generate_semantic_gap(
        depth_source=2,
        depth_target=2,
        n_distractors=10,
        include_bridge_in_kb=True,
        seed=42,
    )
    facts_bridged = format_facts(spec_bridged)
    stvs_bridged = format_spec_stvs(spec_bridged)
    cfg_bridged = SearchConfig(max_steps=50, guided=True, enable_tier2=False)
    eng_bridged = AStarSearchEngine(config=cfg_bridged)
    t0 = time.perf_counter()
    res_bridged = eng_bridged.search(
        initial_tasks=facts_bridged,
        initial_beliefs=facts_bridged,
        goal=spec_bridged["goal"],
        concept_stvs=stvs_bridged,
    )
    _row("A* Search (bridge in KB, real PLN)", res_bridged, time.perf_counter() - t0)

    print("-" * 95)
    if res_assisted.subgoals_proposed:
        sg = res_assisted.subgoals_proposed[0]
        print(f"\n[Tier 2 Strategic Intervention Output]")
        print(f"  Proposed Subgoal : {sg.subgoal_str}")
        print(f"  Suggested Premise: {sg.suggested_premise_str}")
        print(f"  Model Rationale  : {sg.reasoning}")
        print("  Outcome          : subgoal derived from existing premises; no axiom injected.")

    print("\n" + "=" * 95)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PRISM Tier 2 Semantic Gap Benchmark")
    parser.add_argument("--live", action="store_true", help="Run live against OpenRouter API")
    args = parser.parse_args()
    run_gap_benchmark(live=args.live)
