"""
Diamond & Multi-Path DAG Inference Domain Generator for PRISM Benchmarks.

Generates automated reasoning problems featuring competing deduction paths:
a short path (depth k) and a long path (depth m > k) leading to the same goal (A -> Z),
with optional distractors to test search path optimality and branching resistance.
"""

import os
import random
from typing import Any, Dict, List, Optional, Set, Tuple


def get_shortcut_node_name(idx: int) -> str:
    """Return naming convention for shortcut nodes: S1, S2, ..."""
    return f"S{idx}"


def get_longpath_node_name(idx: int) -> str:
    """Return naming convention for long-path nodes: L1, L2, ..."""
    return f"L{idx}"


def generate_diamond(
    depth_short: int = 2,
    depth_long: int = 5,
    base_strength: float = 0.9,
    base_confidence: float = 0.9,
) -> Dict[str, Any]:
    """
    Generate a pure diamond deduction DAG connecting start node 'A' to target 'Z'.

    Parameters
    ----------
    depth_short : int
        Number of deduction steps along the short path (must be >= 2).
        depth_short=2 produces A -> S1 -> Z (2 premise facts, 1 deduction step).
    depth_long : int
        Number of deduction steps along the long path (must be > depth_short).
        depth_long=5 produces A -> L1 -> L2 -> L3 -> L4 -> Z (5 premise facts).
    base_strength : float
        Initial truth strength for path premises.
    base_confidence : float
        Initial truth confidence for path premises.

    Returns
    -------
    Dict[str, Any]
        Metadata dictionary containing facts, nodes, goal, and path classifications.

    Explicit Non-Goals
    ------------------
    - Does not generate random distractors (use generate_diamond_with_distractors).
    - Does not execute derivation or write files to disk.
    """
    if depth_short < 2:
        raise ValueError(f"depth_short must be at least 2, got {depth_short}")
    if depth_long <= depth_short:
        raise ValueError(
            f"depth_long ({depth_long}) must be strictly greater than depth_short ({depth_short})"
        )

    start_node = "A"
    goal_node = "Z"

    # Shortcut nodes: A -> S1 -> S2 -> ... -> S_{k-1} -> Z
    shortcut_intermediates = [get_shortcut_node_name(i + 1) for i in range(depth_short - 1)]
    shortcut_chain = [start_node] + shortcut_intermediates + [goal_node]

    # Long-path nodes: A -> L1 -> L2 -> ... -> L_{m-1} -> Z
    long_intermediates = [get_longpath_node_name(i + 1) for i in range(depth_long - 1)]
    long_chain = [start_node] + long_intermediates + [goal_node]

    all_nodes = [start_node, goal_node] + shortcut_intermediates + long_intermediates
    prior_s = round(1.0 / max(4, len(all_nodes)), 4)
    stv_decls = [f"(= (STV {n}) (stv {prior_s} 0.9))" for n in all_nodes]

    shortcut_facts: List[Dict[str, Any]] = []
    shortcut_evidence_ids: List[str] = []
    evidence_counter = 1

    for i in range(depth_short):
        eid = str(evidence_counter)
        evidence_counter += 1
        shortcut_evidence_ids.append(eid)
        shortcut_facts.append(
            {
                "statement": f"(Inheritance {shortcut_chain[i]} {shortcut_chain[i+1]})",
                "stv": f"(stv {base_strength} {base_confidence})",
                "evidence_id": eid,
                "source": shortcut_chain[i],
                "target": shortcut_chain[i + 1],
                "path": "shortcut",
            }
        )

    long_facts: List[Dict[str, Any]] = []
    long_evidence_ids: List[str] = []
    for i in range(depth_long):
        eid = str(evidence_counter)
        evidence_counter += 1
        long_evidence_ids.append(eid)
        long_facts.append(
            {
                "statement": f"(Inheritance {long_chain[i]} {long_chain[i+1]})",
                "stv": f"(stv {base_strength} {base_confidence})",
                "evidence_id": eid,
                "source": long_chain[i],
                "target": long_chain[i + 1],
                "path": "long",
            }
        )

    goal = f"(Inheritance {start_node} {goal_node})"

    return {
        "domain_type": "diamond_dag",
        "depth_short": depth_short,
        "depth_long": depth_long,
        "start_node": start_node,
        "goal_node": goal_node,
        "goal": goal,
        "nodes": all_nodes,
        "shortcut_nodes": shortcut_chain,
        "long_nodes": long_chain,
        "shortcut_facts": shortcut_facts,
        "long_facts": long_facts,
        "shortcut_evidence_ids": shortcut_evidence_ids,
        "long_evidence_ids": long_evidence_ids,
        "distractor_facts": [],
        "stv_declarations": stv_decls,
        "total_facts": len(shortcut_facts) + len(long_facts),
    }


def generate_diamond_with_distractors(
    depth_short: int = 2,
    depth_long: int = 5,
    n_distractors: int = 20,
    base_strength: float = 0.9,
    base_confidence: float = 0.9,
    seed: Optional[int] = 42,
) -> Dict[str, Any]:
    """
    Generate a diamond DAG enriched with isolated distractor facts.

    Parameters
    ----------
    depth_short : int
        Length of shortcut path.
    depth_long : int
        Length of long path.
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
        Complete specification dictionary including distractor facts.

    Explicit Non-Goals
    ------------------
    - Does not modify path lengths or optimal proof stamps.
    """
    spec = generate_diamond(
        depth_short=depth_short,
        depth_long=depth_long,
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
    evidence_start = 200

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
                "path": "distractor",
            }
        )

    spec["distractor_facts"] = distractor_facts
    spec["total_facts"] = (
        len(spec["shortcut_facts"]) + len(spec["long_facts"]) + len(distractor_facts)
    )
    return spec


def classify_diamond_solution(
    evidence_stamp: Optional[List[str]],
    spec: Dict[str, Any],
) -> str:
    """
    Determine which path was utilized to derive the goal sentence.

    Parameters
    ----------
    evidence_stamp : Optional[List[str]]
        Evidence stamp IDs extracted from the goal Sentence, e.g. ['1', '2'].
    spec : Dict[str, Any]
        The specification generated by generate_diamond.

    Returns
    -------
    str
        'SHORTCUT' if proof used only shortcut premises.
        'LONG_PATH' if proof used only long path premises.
        'MIXED' if proof merged premises from both paths.
        'UNKNOWN' if stamp is empty or unrecognized.
    """
    if not evidence_stamp:
        return "UNKNOWN"

    stamp_set = set(str(e) for e in evidence_stamp)
    shortcut_set = set(spec["shortcut_evidence_ids"])
    long_set = set(spec["long_evidence_ids"])

    is_shortcut = stamp_set.issubset(shortcut_set)
    is_long = stamp_set.issubset(long_set)

    if is_shortcut and not is_long:
        return "SHORTCUT"
    if is_long and not is_shortcut:
        return "LONG_PATH"
    if stamp_set.intersection(shortcut_set) and stamp_set.intersection(long_set):
        return "MIXED"
    return "UNKNOWN"


def generate_diamond_metta_content(
    spec: Dict[str, Any],
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    guided: bool = True,
) -> str:
    """
    Render runnable MeTTa benchmark file content from a diamond domain spec.

    Parameters
    ----------
    spec : Dict[str, Any]
        Output of generate_diamond or generate_diamond_with_distractors.
    max_steps : int
        Derivation search budget.
    task_queue_size : int
        Priority queue capacity.
    belief_queue_size : int
        Belief buffer capacity.
    guided : bool
        If True, guides search with goal. If False, runs unguided baseline.

    Returns
    -------
    str
        Formatted MeTTa source code.
    """
    all_facts = spec["shortcut_facts"] + spec["long_facts"] + spec["distractor_facts"]

    lines = [
        ";; Auto-generated PRISM Benchmark Diamond DAG Domain",
        (
            f";; Shortcut Depth: {spec['depth_short']} | "
            f"Long Depth: {spec['depth_long']} | "
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


def write_diamond_metta_file(
    spec: Dict[str, Any],
    output_path: str,
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    guided: bool = True,
) -> str:
    """Generate and write a diamond domain .metta file to disk."""
    content = generate_diamond_metta_content(
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
