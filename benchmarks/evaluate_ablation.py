"""
4-Way Component Ablation Benchmark for PRISM.

Evaluates each search configuration independently across 4 reasoning topologies:
1. Unguided Search (guided=False, use_stage0_filter=False)
2. Stage 0 Only (guided=False, use_stage0_filter=True)
3. Tier 1 A* Only (guided=True, use_stage0_filter=False)
4. Full PRISM A* (guided=True, use_stage0_filter=True)
"""

import time
from typing import Any, Dict, List

from prism.benchmarks.domains.multipath_dag import generate_diamond_with_distractors
from prism.benchmarks.domains.transitive_chain import generate_with_distractors
from prism.benchmarks.domains.tree_dag import generate_tree_with_distractors
from prism.benchmarks.evaluate_search_comparison import format_spec_facts, format_spec_stvs
from prism.core.config import SearchConfig
from prism.search.engine import AStarSearchEngine


def run_ablation():
    scenarios = [
        ("Linear Chain D=4 (10 Distractors)", generate_with_distractors(depth=4, n_distractors=10, seed=42)),
        ("Linear Chain D=6 (25 Distractors)", generate_with_distractors(depth=6, n_distractors=25, seed=42)),
        ("Diamond DAG D_short=3 vs D_long=7 (30 Distractors)", generate_diamond_with_distractors(depth_short=3, depth_long=7, n_distractors=30, seed=42)),
        ("Tree Conjunction L(3,3) (20 Distractors)", generate_tree_with_distractors(depth_left=3, depth_right=3, n_distractors=20, seed=42)),
    ]

    configs = [
        ("Unguided Baseline", SearchConfig(guided=False, use_stage0_filter=False, max_steps=200, beam_width=5)),
        ("Stage 0 Only",     SearchConfig(guided=False, use_stage0_filter=True,  max_steps=200, beam_width=5)),
        ("Tier 1 A* Only",   SearchConfig(guided=True,  use_stage0_filter=False, max_steps=200, beam_width=5)),
        ("Full PRISM A*",    SearchConfig(guided=True,  use_stage0_filter=True,  max_steps=200, beam_width=5)),
    ]

    print("=" * 95)
    print("PRISM 4-WAY COMPONENT ABLATION BENCHMARK")
    print("=" * 95)

    for name, spec in scenarios:
        facts = format_spec_facts(spec)
        stvs = format_spec_stvs(spec)
        goal = spec["goal"]
        distractor_count = len(spec.get("distractor_facts", []))
        print(f"\nScenario: {name}")
        print(f"Goal: {goal} | Initial Facts: {len(facts)} | Distractors: {distractor_count}")
        print("-" * 95)
        print(f"{'Configuration':<22} | {'Success':<7} | {'Steps':<7} | {'Nodes Gen':<10} | {'Visited':<8} | {'Time (s)':<9}")
        print("-" * 95)

        for label, cfg in configs:
            engine = AStarSearchEngine(config=cfg)
            t0 = time.perf_counter()
            res = engine.search(
                initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs
            )
            elapsed = time.perf_counter() - t0

            status = "PASS" if res.goal_found else "FAIL"
            print(f"{label:<22} | {status:<7} | {res.steps_expanded:<7} | {res.nodes_generated:<10} | {res.visited_states_count:<8} | {elapsed:.4f}s")
        print("-" * 95)

    print("\n" + "=" * 95)


if __name__ == "__main__":
    run_ablation()
