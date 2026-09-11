"""
Empirical Comparison: Unguided / Uniform-Cost Search vs. PRISM Learned A* Search.

Evaluates how Tier 1 heuristic guidance and A* path-cost management reduce
state space expansion, avoid distractors, and discover optimal proof paths.
"""

import time
from typing import Any, Dict, List

from prism.benchmarks.domains.multipath_dag import generate_diamond_with_distractors
from prism.benchmarks.domains.transitive_chain import generate_with_distractors
from prism.benchmarks.domains.tree_dag import generate_tree_with_distractors
from prism.core.config import SearchConfig
from prism.search.engine import AStarSearchEngine, SearchResult


def format_spec_facts(spec: Dict[str, Any]) -> List[Any]:
    """Convert domain generator facts into Python S-expression lists."""
    facts = []
    # Collect all facts from the domain specification
    raw_facts = (
        spec.get("chain_facts", [])
        + spec.get("shortcut_facts", [])
        + spec.get("long_facts", [])
        + spec.get("left_facts", [])
        + spec.get("right_facts", [])
        + spec.get("distractor_facts", [])
    )

    for f in raw_facts:
        stmt = f["statement"]  # e.g. '(Inheritance A B)'
        stv = f["stv"]          # e.g. '(stv 0.9 0.9)'
        eid = f["evidence_id"]  # e.g. '1'
        # Parse into S-expression format: (Sentence ((Rel A B) (stv s c)) (eid))
        parts = stmt.strip("()").split()
        rel, sub, obj = parts[0], parts[1], parts[2]
        stv_parts = stv.strip("()").split()
        s, c = float(stv_parts[1]), float(stv_parts[2])
        facts.append(["Sentence", [[rel, sub, obj], ["stv", s, c]], [str(eid)]])

    return facts


def run_comparison(domain_name: str, spec: Dict[str, Any], max_steps: int = 100) -> Dict[str, Any]:
    """Run head-to-head comparison between Unguided Search and PRISM A* Search."""
    facts = format_spec_facts(spec)
    goal = spec["goal"]

    # 1. Unguided Search (h(n) = 0.0, Uniform-Cost Search / FIFO beam)
    cfg_unguided = SearchConfig(max_steps=max_steps, beam_width=5, guided=False)
    engine_unguided = AStarSearchEngine(config=cfg_unguided)
    res_unguided = engine_unguided.search(initial_tasks=facts, initial_beliefs=facts, goal=goal)

    # 2. PRISM Learned A* Search (f(n) = g(n) + h(n), Tier 1 guided)
    cfg_guided = SearchConfig(max_steps=max_steps, beam_width=5, guided=True)
    engine_guided = AStarSearchEngine(config=cfg_guided)
    res_guided = engine_guided.search(initial_tasks=facts, initial_beliefs=facts, goal=goal)

    return {
        "domain": domain_name,
        "total_initial_facts": len(facts),
        "distractors": len(spec.get("distractor_facts", [])),
        "goal": goal,
        "unguided": {
            "success": res_unguided.goal_found,
            "steps_expanded": res_unguided.steps_expanded,
            "nodes_generated": res_unguided.nodes_generated,
            "visited_count": res_unguided.visited_states_count,
            "wall_clock": res_unguided.wall_clock_seconds,
            "proof_length": len(res_unguided.proof_path),
        },
        "guided": {
            "success": res_guided.goal_found,
            "steps_expanded": res_guided.steps_expanded,
            "nodes_generated": res_guided.nodes_generated,
            "visited_count": res_guided.visited_states_count,
            "wall_clock": res_guided.wall_clock_seconds,
            "proof_length": len(res_guided.proof_path),
        },
    }


def main():
    print("=" * 85)
    print("EMPIRICAL COMPARISON: UNGUIDED SEARCH vs. PRISM LEARNED A* SEARCH")
    print("=" * 85)

    scenarios = []

    # Scenario 1: Linear Transitive Chain D=4 with 10 distractors
    spec_chain4 = generate_with_distractors(depth=4, n_distractors=10, seed=42)
    scenarios.append(("Linear Chain D=4 (10 Distractors)", spec_chain4))

    # Scenario 2: Linear Transitive Chain D=6 with 25 distractors
    spec_chain6 = generate_with_distractors(depth=6, n_distractors=25, seed=42)
    scenarios.append(("Linear Chain D=6 (25 Distractors)", spec_chain6))

    # Scenario 3: Diamond Domain (Shortcut D=3 vs Long D=7) with 30 distractors
    spec_diamond = generate_diamond_with_distractors(
        depth_short=3, depth_long=7, n_distractors=30, seed=42
    )
    scenarios.append(("Diamond DAG D_short=3 vs D_long=7 (30 Distractors)", spec_diamond))

    # Scenario 4: Tree Conjunction Domain (Branch 1 D=3, Branch 2 D=3) with 20 distractors
    spec_tree = generate_tree_with_distractors(
        depth_left=3, depth_right=3, n_distractors=20, seed=42
    )
    scenarios.append(("Tree Conjunction L(3,3) (20 Distractors)", spec_tree))

    results = []
    for name, spec in scenarios:
        res = run_comparison(name, spec, max_steps=80)
        results.append(res)

        u = res["unguided"]
        g = res["guided"]

        step_reduction = (
            f"{((u['steps_expanded'] - g['steps_expanded']) / max(1, u['steps_expanded'])) * 100:.1f}%"
            if u["steps_expanded"] > 0
            else "N/A"
        )
        node_reduction = (
            f"{((u['nodes_generated'] - g['nodes_generated']) / max(1, u['nodes_generated'])) * 100:.1f}%"
            if u["nodes_generated"] > 0
            else "N/A"
        )

        print(f"\nScenario: {name}")
        print(f"Goal: {res['goal']} | Total Facts: {res['total_initial_facts']} | Distractors: {res['distractors']}")
        print(f"  [Unguided Search] Success: {u['success']} | Steps: {u['steps_expanded']} | Nodes Gen: {u['nodes_generated']} | Time: {u['wall_clock']}s")
        print(f"  [PRISM A* Search] Success: {g['success']} | Steps: {g['steps_expanded']} | Nodes Gen: {g['nodes_generated']} | Time: {g['wall_clock']}s")
        print(f"  --> Efficiency Gain: Step Reduction = {step_reduction} | Search Space Reduction = {node_reduction}")

    print("\n" + "=" * 85)


if __name__ == "__main__":
    main()
