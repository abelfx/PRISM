"""
Semantic Gap Benchmark Domain Generator for PRISM Tier 2.

Generates inference scenarios containing semantic chasms or disconnected
sub-graphs where local symbolic heuristics stall, requiring Tier 2 LLM
strategic subgoal or premise proposals to bridge the gap.
"""

import random
from typing import Any, Dict, List, Optional, Set


def generate_semantic_gap(
    depth_source: int = 2,
    depth_target: int = 2,
    n_distractors: int = 20,
    n_goal_decoys: int = 0,
    include_bridge_in_kb: bool = False,
    include_bridge_support: bool = False,
    seed: int = 42,
    base_strength: float = 0.9,
    base_confidence: float = 0.9,
) -> Dict[str, Any]:
    """
    Generate a two-cluster reasoning graph with a missing or unguided bridge lemma.

    Source Cluster: S_0 -> S_1 -> ... -> S_k (e.g. A -> B -> C)
    Target Cluster: T_0 -> T_1 -> ... -> T_m (e.g. M -> N -> Z)
    Bridge: S_k -> T_0 (e.g. C -> M)
    Goal: S_0 -> T_m (e.g. A -> Z)

    Args:
        depth_source: Length of premise chain in source cluster.
        depth_target: Length of premise chain in target cluster.
        n_distractors: Number of background distractor facts to inject.
        n_goal_decoys: Number of high-confidence dead-end chains rooted at the
            goal source. These are deliberately hard for goal-overlap scoring.
        include_bridge_in_kb: If True, the completed bridge is an input fact.
        include_bridge_support: If True, two input premises make the bridge
            legally derivable, but the completed bridge is not an input fact.
        seed: Random seed for reproducibility.

    Returns:
        Dict with facts, goal, bridge, and metadata.
    """
    rng = random.Random(seed)

    source_nodes = ["A", "B", "C"][: depth_source + 1]
    if len(source_nodes) < depth_source + 1:
        source_nodes += [f"S{i}" for i in range(len(source_nodes), depth_source + 1)]

    target_nodes = ["M", "N", "Z"][: depth_target + 1]
    if len(target_nodes) < depth_target + 1:
        target_nodes += [f"T{i}" for i in range(len(target_nodes), depth_target + 1)]

    bridge_source = source_nodes[-1]
    bridge_target = target_nodes[0]
    goal_source = source_nodes[0]
    goal_target = target_nodes[-1]

    source_facts = []
    eid = 1
    for i in range(len(source_nodes) - 1):
        source_facts.append({
            "statement": f"(Inheritance {source_nodes[i]} {source_nodes[i+1]})",
            "stv": f"(stv {base_strength} {base_confidence})",
            "evidence_id": str(eid),
            "cluster": "source",
        })
        eid += 1

    target_facts = []
    for i in range(len(target_nodes) - 1):
        target_facts.append({
            "statement": f"(Inheritance {target_nodes[i]} {target_nodes[i+1]})",
            "stv": f"(stv {base_strength} {base_confidence})",
            "evidence_id": str(eid),
            "cluster": "target",
        })
        eid += 1

    bridge_fact = {
        "statement": f"(Inheritance {bridge_source} {bridge_target})",
        "stv": f"(stv {base_strength} {base_confidence})",
        "evidence_id": str(eid),
        "cluster": "bridge",
    }
    eid += 1

    bridge_midpoint = "H"
    bridge_support_facts = [
        {
            "statement": f"(Inheritance {bridge_source} {bridge_midpoint})",
            "stv": f"(stv {base_strength} {base_confidence})",
            "evidence_id": str(eid),
            "cluster": "bridge_support",
        },
        {
            "statement": f"(Inheritance {bridge_midpoint} {bridge_target})",
            "stv": f"(stv {base_strength} {base_confidence})",
            "evidence_id": str(eid + 1),
            "cluster": "bridge_support",
        },
    ]
    eid += 2

    distractor_facts = []
    for i in range(n_distractors):
        x = f"DistX{i}"
        y = f"DistY{i}"
        s = round(rng.uniform(0.4, 0.9), 4)
        c = round(rng.uniform(0.7, 0.98), 4)  # high confidence distractors
        distractor_facts.append({
            "statement": f"(Inheritance {x} {y})",
            "stv": f"(stv {s} {c})",
            "evidence_id": str(eid),
            "cluster": "distractor",
        })
        eid += 1

    for i in range(n_goal_decoys):
        midpoint = f"DecoyMid{i}"
        endpoint = f"DecoyEnd{i}"
        distractor_facts.extend(
            [
                {
                    "statement": f"(Inheritance {goal_source} {midpoint})",
                    "stv": "(stv 0.99 0.99)",
                    "evidence_id": str(eid),
                    "cluster": "goal_decoy",
                },
                {
                    "statement": f"(Inheritance {midpoint} {endpoint})",
                    "stv": "(stv 0.99 0.99)",
                    "evidence_id": str(eid + 1),
                    "cluster": "goal_decoy",
                },
            ]
        )
        eid += 2

    facts = list(source_facts) + list(target_facts)
    if include_bridge_in_kb:
        facts.append(bridge_fact)
    if include_bridge_support:
        facts.extend(bridge_support_facts)
    facts.extend(distractor_facts)

    proof_nodes = list(dict.fromkeys(source_nodes + target_nodes + [bridge_midpoint]))
    prior_s = round(1.0 / max(len(proof_nodes), 1), 4)
    stv_decls = [f"(= (STV {n}) (stv {prior_s} 0.9))" for n in proof_nodes]
    distractor_concepts = []
    for f in distractor_facts:
        parts = f["statement"].strip("()").split()
        distractor_concepts.extend(parts[1:3])
    goal_decoy_concepts = {
        concept
        for fact in distractor_facts
        if fact["cluster"] == "goal_decoy"
        for concept in fact["statement"].strip("()").split()[1:3]
        if concept != goal_source
    }
    stv_decls.extend(
        f"(= (STV {c}) (stv 0.9 0.99))"
        if c in goal_decoy_concepts
        else f"(= (STV {c}) (stv 0.1 0.9))"
        for c in dict.fromkeys(distractor_concepts)
    )

    return {
        "domain": "semantic_gap",
        "goal": ["Inheritance", goal_source, goal_target],
        "goal_str": f"(Inheritance {goal_source} {goal_target})",
        "source_nodes": source_nodes,
        "target_nodes": target_nodes,
        "bridge_fact": bridge_fact,
        "bridge_support_facts": bridge_support_facts,
        "bridge_subgoal": ["Inheritance", bridge_source, bridge_target],
        "bridge_subgoal_str": f"(Inheritance {bridge_source} {bridge_target})",
        "source_facts": source_facts,
        "target_facts": target_facts,
        "distractor_facts": distractor_facts,
        "facts": facts,
        "stv_declarations": stv_decls,
        "include_bridge_in_kb": include_bridge_in_kb,
        "include_bridge_support": include_bridge_support,
    }
