"""
Synthetic Transitive Inference Chain Generator for PRISM Benchmarks.
Generates controllable inference problems at depths D in [5, 20]
with optional distractor facts to test branching resistance.
"""

import os
import random
import string
from typing import Any, Dict, List, Optional, Set


def get_node_name(idx: int) -> str:
    """Return alphabetical node name for idx < 26, else N{idx}."""
    if idx < 26:
        return string.ascii_uppercase[idx]
    return f"N{idx}"


def generate_chain(
    depth: int,
    base_strength: float = 0.9,
    base_confidence: float = 0.9,
) -> Dict[str, Any]:
    """
    Generate a pure transitive inference chain of given depth.

    Parameters
    ----------
    depth : int
        Number of inference steps from source to target.
        depth=5 creates nodes [A, B, C, D, E, F] and 5 facts:
        A->B, B->C, C->D, D->E, E->F.
    base_strength : float
        Initial truth strength for chain premises.
    base_confidence : float
        Initial truth confidence for chain premises.

    Returns
    -------
    Dict with chain metadata, facts, STVs, goal, and optimal path info.
    """
    num_nodes = depth + 1
    nodes = [get_node_name(i) for i in range(num_nodes)]

    # Prior probability for STVs: 1 / num_nodes
    prior_s = round(1.0 / num_nodes, 4)
    stv_decls = [f"(= (STV {n}) (stv {prior_s} 0.9))" for n in nodes]

    chain_facts = []
    for i in range(depth):
        chain_facts.append(
            {
                "statement": f"(Inheritance {nodes[i]} {nodes[i+1]})",
                "stv": f"(stv {base_strength} {base_confidence})",
                "evidence_id": str(i + 1),
                "source": nodes[i],
                "target": nodes[i + 1],
            }
        )

    goal = f"(Inheritance {nodes[0]} {nodes[-1]})"

    # Set of nodes participating in the valid proof
    proof_nodes = set(nodes)

    return {
        "depth": depth,
        "nodes": nodes,
        "proof_nodes": list(proof_nodes),
        "chain_facts": chain_facts,
        "distractor_facts": [],
        "stv_declarations": stv_decls,
        "goal": goal,
        "start_node": nodes[0],
        "end_node": nodes[-1],
        "optimal_proof_steps": depth - 1,
        "total_facts": len(chain_facts),
    }


def generate_with_distractors(
    depth: int,
    n_distractors: int = 50,
    base_strength: float = 0.9,
    base_confidence: float = 0.9,
    seed: Optional[int] = 42,
) -> Dict[str, Any]:
    """
    Generate a transitive chain enriched with random distractor facts.

    Parameters
    ----------
    depth : int
        Length of the gold inference chain.
    n_distractors : int
        Number of unrelated facts to insert into the knowledge base.
    seed : Optional[int]
        Random seed for reproducible distractor generation.
    """
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    spec = generate_chain(depth, base_strength, base_confidence)
    if n_distractors <= 0:
        return spec

    # Generate distractor concepts (D0, D1, ...)
    num_distractor_concepts = max(10, n_distractors // 2)
    distractor_concepts = [f"D{i}" for i in range(num_distractor_concepts)]

    # STV declarations for distractor concepts
    distractor_stvs = [
        f"(= (STV {c}) (stv 0.1 0.9))" for c in distractor_concepts
    ]
    spec["stv_declarations"].extend(distractor_stvs)

    distractor_facts = []
    evidence_start = 100

    existing_pairs: Set[tuple] = set()
    for f in spec["chain_facts"]:
        existing_pairs.add((f["source"], f["target"]))

    for i in range(n_distractors):
        # Pick two distinct distractor concepts
        a = rng.choice(distractor_concepts)
        b = rng.choice(distractor_concepts)
        while a == b:
            b = rng.choice(distractor_concepts)

        # Distractor strength and confidence
        s = round(rng.uniform(0.2, 0.95), 2)
        c = round(rng.uniform(0.4, 0.95), 2)

        distractor_facts.append(
            {
                "statement": f"(Inheritance {a} {b})",
                "stv": f"(stv {s} {c})",
                "evidence_id": str(evidence_start + i),
                "source": a,
                "target": b,
            }
        )

    spec["distractor_facts"] = distractor_facts
    spec["total_facts"] = len(spec["chain_facts"]) + len(distractor_facts)
    return spec


def generate_metta_content(
    spec: Dict[str, Any],
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    guided: bool = True,
) -> str:
    """
    Render a complete runnable MeTTa benchmark file from a chain spec.

    Parameters
    ----------
    spec : Dict[str, Any]
        Output of generate_chain or generate_with_distractors.
    max_steps : int
        Search step budget for PLN.
    guided : bool
        If True, passes the goal to PLN.Query.
        If False, runs unguided (Goal = ()) for baseline measurement.
    """
    all_facts = spec["chain_facts"] + spec["distractor_facts"]

    lines = [
        ";; Auto-generated PRISM Benchmark Transitive Chain",
        f";; Depth: {spec['depth']} | Distractors: {len(spec['distractor_facts'])} | Guided: {guided}",
        "!(import! &self (library lib_import))",
        '!(git-import! "https://github.com/trueagi-io/PLN.git")',
        "!(import! &self (library PLN lib_pln))",
        "",
        ";; STV Declarations for concepts",
    ]
    lines.extend(spec["stv_declarations"])
    lines.append("")
    lines.append(";; Knowledge Base")
    lines.append("(= (kb) (")
    for f in all_facts:
        lines.append(f"    (Sentence ({f['statement']} {f['stv']}) ({f['evidence_id']}))")
    lines.append("))")
    lines.append("")

    goal = spec["goal"]
    if guided:
        # Standard goal-directed query forwarding goal to PLN.Derive
        query_expr = f"(PLN.Query (kb) {goal} {max_steps} {task_queue_size} {belief_queue_size})"
    else:
        # Explicitly unguided query (passing () as goal to PLN.Derive)
        query_expr = (
            f"(BestConfidenceCandidate "
            f"(collapse (let ($TasksRet $BeliefsRet) "
            f"(PLN.Derive (kb) (kb) 1 {max_steps} {task_queue_size} {belief_queue_size} ()) "
            f'(case (superpose $BeliefsRet) (((Sentence ($Term $TV) $Ev) (case (== $Term {goal}) ((True ($TV $Ev))))))))))'
        )

    lines.append(f";; Target Goal: {goal}")
    lines.append(f"!(println! (BENCHMARK_TARGET_GOAL: {goal}))")
    lines.append(f"!(println! (BENCHMARK_RESULT: {query_expr}))")

    return "\n".join(lines) + "\n"


def write_metta_file(
    spec: Dict[str, Any],
    output_path: str,
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    guided: bool = True,
) -> str:
    """Generate and write a .metta file to disk."""
    content = generate_metta_content(
        spec,
        max_steps=max_steps,
        task_queue_size=task_queue_size,
        belief_queue_size=belief_queue_size,
        guided=guided,
    )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(content)
    return output_path
