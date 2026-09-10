"""
Tree & Conjunctive Subgoal Domain Generator for PRISM Benchmarks.

Generates multi-branch derivation problems where reaching the target goal (A -> Z)
requires synthesizing intermediate lemmas derived from two independent branches
converging at a junction concept:
  Branch 1: A -> L1 -> ... -> M (derives A -> M)
  Branch 2: M -> R1 -> ... -> Z (derives M -> Z)
  Final:    (A -> M) + (M -> Z) |- (A -> Z)
"""

import os
import random
from typing import Any, Dict, List, Optional, Set


def get_left_node_name(idx: int) -> str:
    """Return naming convention for left branch nodes: L1, L2, ..."""
    return f"L{idx}"


def get_right_node_name(idx: int) -> str:
    """Return naming convention for right branch nodes: R{idx}."""
    return f"R{idx}"


def generate_tree_conjunction(
    depth_left: int = 2,
    depth_right: int = 2,
    base_strength: float = 0.9,
    base_confidence: float = 0.9,
) -> Dict[str, Any]:
    """
    Generate a 2-branch confluent derivation DAG converging at a junction concept.

    Parameters
    ----------
    depth_left : int
        Number of deduction steps in Branch 1 (A -> ... -> M). Must be >= 1.
    depth_right : int
        Number of deduction steps in Branch 2 (M -> ... -> Z). Must be >= 1.
    base_strength : float
        Initial truth strength for premises.
    base_confidence : float
        Initial truth confidence for premises.

    Returns
    -------
    Dict[str, Any]
        Metadata dictionary containing facts, branches, and junction node info.

    Explicit Non-Goals
    ------------------
    - Does not generate random distractors (use generate_tree_with_distractors).
    - Does not execute derivation or write files to disk.
    """
    if depth_left < 1:
        raise ValueError(f"depth_left must be at least 1, got {depth_left}")
    if depth_right < 1:
        raise ValueError(f"depth_right must be at least 1, got {depth_right}")

    start_node = "A"
    junction_node = "M"
    goal_node = "Z"

    # Branch 1 nodes: A -> L1 -> ... -> L_{depth_left - 1} -> M
    left_intermediates = [get_left_node_name(i + 1) for i in range(depth_left - 1)]
    left_chain = [start_node] + left_intermediates + [junction_node]

    # Branch 2 nodes: M -> R1 -> ... -> R_{depth_right - 1} -> Z
    right_intermediates = [get_right_node_name(i + 1) for i in range(depth_right - 1)]
    right_chain = [junction_node] + right_intermediates + [goal_node]

    all_nodes = [start_node, junction_node, goal_node] + left_intermediates + right_intermediates
    prior_s = round(1.0 / max(4, len(all_nodes)), 4)
    stv_decls = [f"(= (STV {n}) (stv {prior_s} 0.9))" for n in all_nodes]

    left_facts: List[Dict[str, Any]] = []
    left_evidence_ids: List[str] = []
    evidence_counter = 1

    for i in range(depth_left):
        eid = str(evidence_counter)
        evidence_counter += 1
        left_evidence_ids.append(eid)
        left_facts.append(
            {
                "statement": f"(Inheritance {left_chain[i]} {left_chain[i+1]})",
                "stv": f"(stv {base_strength} {base_confidence})",
                "evidence_id": eid,
                "source": left_chain[i],
                "target": left_chain[i + 1],
                "branch": "left",
            }
        )

    right_facts: List[Dict[str, Any]] = []
    right_evidence_ids: List[str] = []
    for i in range(depth_right):
        eid = str(evidence_counter)
        evidence_counter += 1
        right_evidence_ids.append(eid)
        right_facts.append(
            {
                "statement": f"(Inheritance {right_chain[i]} {right_chain[i+1]})",
                "stv": f"(stv {base_strength} {base_confidence})",
                "evidence_id": eid,
                "source": right_chain[i],
                "target": right_chain[i + 1],
                "branch": "right",
            }
        )

    goal = f"(Inheritance {start_node} {goal_node})"

    return {
        "domain_type": "tree_conjunction",
        "depth_left": depth_left,
        "depth_right": depth_right,
        "start_node": start_node,
        "junction_node": junction_node,
        "goal_node": goal_node,
        "goal": goal,
        "nodes": all_nodes,
        "left_nodes": left_chain,
        "right_nodes": right_chain,
        "left_facts": left_facts,
        "right_facts": right_facts,
        "left_evidence_ids": left_evidence_ids,
        "right_evidence_ids": right_evidence_ids,
        "required_evidence_ids": left_evidence_ids + right_evidence_ids,
        "distractor_facts": [],
        "stv_declarations": stv_decls,
        "total_facts": len(left_facts) + len(right_facts),
    }


def generate_tree_with_distractors(
    depth_left: int = 2,
    depth_right: int = 2,
    n_distractors: int = 20,
    base_strength: float = 0.9,
    base_confidence: float = 0.9,
    seed: Optional[int] = 42,
) -> Dict[str, Any]:
    """
    Generate a tree conjunction domain enriched with random distractor facts.

    Parameters
    ----------
    depth_left : int
        Length of Branch 1.
    depth_right : int
        Length of Branch 2.
    n_distractors : int
        Number of irrelevant facts to inject.
    base_strength : float
        Truth strength for path facts.
    base_confidence : float
        Confidence for path facts.
    seed : Optional[int]
        Random seed for reproducibility.

    Returns
    -------
    Dict[str, Any]
        Specification dictionary including distractor facts.
    """
    spec = generate_tree_conjunction(
        depth_left=depth_left,
        depth_right=depth_right,
        base_strength=base_strength,
        base_confidence=base_confidence,
    )

    if n_distractors <= 0:
        return spec

    rng = random.Random(seed)
    num_distractor_concepts = max(10, n_distractors // 2)
    distractor_concepts = [f"D{i}" for i in range(num_distractor_concepts)]

    distractor_stvs = [f"(= (STV {c}) (stv 0.1 0.9))" for c in distractor_concepts]
    spec["stv_declarations"].extend(distractor_stvs)

    distractor_facts = []
    evidence_start = 300

    for i in range(n_distractors):
        a = rng.choice(distractor_concepts)
        b = rng.choice(distractor_concepts)
        while a == b:
            b = rng.choice(distractor_concepts)

        s = round(rng.uniform(0.2, 0.95), 2)
        c = round(rng.uniform(0.4, 0.95), 2)

        distractor_facts.append(
            {
                "statement": f"(Inheritance {a} {b})",
                "stv": f"(stv {s} {c})",
                "evidence_id": str(evidence_start + i),
                "source": a,
                "target": b,
                "branch": "distractor",
            }
        )

    spec["distractor_facts"] = distractor_facts
    spec["total_facts"] = (
        len(spec["left_facts"]) + len(spec["right_facts"]) + len(distractor_facts)
    )
    return spec


def verify_tree_conjunction_solution(
    evidence_stamp: Optional[List[str]],
    spec: Dict[str, Any],
) -> bool:
    """
    Verify that the derived goal sentence integrated premises from both branches.

    Parameters
    ----------
    evidence_stamp : Optional[List[str]]
        Evidence stamp IDs extracted from the goal Sentence.
    spec : Dict[str, Any]
        Tree conjunction domain specification.

    Returns
    -------
    bool
        True if the proof contains at least one premise from the left branch
        AND at least one premise from the right branch.
    """
    if not evidence_stamp:
        return False

    stamp_set = set(str(e) for e in evidence_stamp)
    left_set = set(spec["left_evidence_ids"])
    right_set = set(spec["right_evidence_ids"])

    has_left = bool(stamp_set.intersection(left_set))
    has_right = bool(stamp_set.intersection(right_set))

    return has_left and has_right


def generate_tree_metta_content(
    spec: Dict[str, Any],
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    guided: bool = True,
) -> str:
    """Render runnable MeTTa benchmark file content from a tree domain spec."""
    all_facts = spec["left_facts"] + spec["right_facts"] + spec["distractor_facts"]

    lines = [
        ";; Auto-generated PRISM Benchmark Tree Conjunction Domain",
        (
            f";; Left Depth: {spec['depth_left']} | "
            f"Right Depth: {spec['depth_right']} | "
            f"Distractors: {len(spec['distractor_facts'])} | Guided: {guided}"
        ),
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
        query_expr = f"(PLN.Query (kb) {goal} {max_steps} {task_queue_size} {belief_queue_size})"
    else:
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


def write_tree_metta_file(
    spec: Dict[str, Any],
    output_path: str,
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    guided: bool = True,
) -> str:
    """Generate and write a tree conjunction domain .metta file to disk."""
    content = generate_tree_metta_content(
        spec,
        max_steps=max_steps,
        task_queue_size=task_queue_size,
        belief_queue_size=belief_queue_size,
        guided=guided,
    )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path
