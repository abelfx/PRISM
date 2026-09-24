"""
PRISM Week 8 Benchmark: Bidirectional A* Search Engine Evaluation.

Evaluates deep derivation scaling across depths D in [6, 8, 10, 12] with 20 distractor facts:
  1. Unidirectional Forward A* (Stage 0 + Tier 1 v1)
  2. Bidirectional A* (Meet-in-the-Middle Convergence + Proof Stitching)

Measures:
  - Success Rate
  - Steps Expanded (Total, Forward, Backward)
  - Nodes Generated (Search Space Size)
  - Proof Length
  - Expensive forward PLN expansion reduction %
  - Total dual-frontier bookkeeping overhead %
  - Wall Clock Time
"""

import time
from typing import Any, Dict, List

from prism.benchmarks.domains.transitive_chain import generate_with_distractors
from prism.benchmarks.evaluate_search_comparison import format_spec_facts, format_spec_stvs
from prism.core.config import BidirectionalConfig, SearchConfig
from prism.search.bidirectional import BidirectionalSearchEngine
from prism.search.engine import AStarSearchEngine


def run_benchmark_depth(depth: int, n_distractors: int = 20, seed: int = 42) -> Dict[str, Any]:
    """Execute unidirectional vs bidirectional search comparison for a given depth."""
    spec = generate_with_distractors(depth=depth, n_distractors=n_distractors, seed=seed)
    facts = format_spec_facts(spec)
    stvs = format_spec_stvs(spec)
    goal = spec["goal"]

    # 1. Unidirectional Forward A* Search
    fwd_cfg = SearchConfig(max_steps=120, beam_width=5, guided=True, use_stage0_filter=True)
    fwd_engine = AStarSearchEngine(config=fwd_cfg)

    t0 = time.perf_counter()
    fwd_res = fwd_engine.search(
        initial_tasks=facts, initial_beliefs=facts, goal=goal, concept_stvs=stvs
    )
    t_fwd = time.perf_counter() - t0

    # 2. Bidirectional A* Search
    bwd_cfg = BidirectionalConfig(max_steps=120, forward_backward_ratio=1.0)
    bwd_engine = BidirectionalSearchEngine(config=bwd_cfg)

    t1 = time.perf_counter()
    bwd_res = bwd_engine.search(goal, facts, concept_stvs=stvs)
    t_bwd = time.perf_counter() - t1

    # Backward decomposition is symbolic and cheap; forward expansions invoke
    # live PLN.Apply over candidate pairs. Report them independently rather
    # than pretending a linear proof can require 50% fewer total logical steps.
    forward_expansion_red = (
        (fwd_res.steps_expanded - bwd_res.forward_steps) / fwd_res.steps_expanded
        if fwd_res.steps_expanded > 0
        else 0.0
    )
    total_step_overhead = (
        (bwd_res.steps_expanded - fwd_res.steps_expanded) / fwd_res.steps_expanded
        if fwd_res.steps_expanded > 0
        else 0.0
    )

    return {
        "depth": depth,
        "distractors": n_distractors,
        "facts_count": len(facts),
        "fwd": {
            "success": fwd_res.goal_found,
            "steps": fwd_res.steps_expanded,
            "nodes": fwd_res.nodes_generated,
            "proof_len": len(fwd_res.proof_path),
            "time": round(t_fwd, 4),
        },
        "bwd": {
            "success": bwd_res.goal_found,
            "steps": bwd_res.steps_expanded,
            "fwd_steps": bwd_res.forward_steps,
            "bwd_steps": bwd_res.backward_steps,
            "nodes": bwd_res.nodes_generated,
            "proof_len": len(bwd_res.proof_path),
            "meeting": bwd_res.meeting_point is not None,
            "time": round(t_bwd, 4),
        },
        "forward_expansion_reduction": forward_expansion_red,
        "total_step_overhead": total_step_overhead,
    }


def main():
    print("=" * 105)
    print("PRISM WEEK 8: BIDIRECTIONAL A* SEARCH DEEP SCALING BENCHMARK")
    print("=" * 105)
    print(f"{'Depth':<7} | {'Configuration':<26} | {'Success':<7} | {'Steps':<7} | {'Fwd/Bwd':<9} | {'Nodes':<7} | {'Proof':<7} | {'Time (s)':<9}")
    print("-" * 105)

    depths = [6, 8, 10, 12]
    all_results = []

    for d in depths:
        res = run_benchmark_depth(depth=d, n_distractors=20, seed=42)
        all_results.append(res)

        f = res["fwd"]
        b = res["bwd"]

        f_status = "[PASS]" if f["success"] else "[FAIL]"
        b_status = "[PASS]" if b["success"] else "[FAIL]"

        print(f"D={d:<5} | {'Unidirectional Forward A*':<26} | {f_status:<7} | {f['steps']:<7} | {'N/A':<9} | {f['nodes']:<7} | {f['proof_len']:<7} | {f['time']:.4f}s")
        print(f"D={d:<5} | {'Bidirectional A* (PRISM)':<26} | {b_status:<7} | {b['steps']:<7} | {f'{b['fwd_steps']}/{b['bwd_steps']}':<9} | {b['nodes']:<7} | {b['proof_len']:<7} | {b['time']:.4f}s")
        print(
            "       -> Efficiency: Forward PLN Expansion Reduction = "
            f"{res['forward_expansion_reduction']:.1%} | "
            f"Total Step Overhead = {res['total_step_overhead']:.1%}"
        )
        print("-" * 105)

    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    main()
