"""
Metrics Collector and Log Parser for PRISM Benchmarks.
Tracks proof search metrics: waste ratio, steps, rules fired, frontier sizes,
and wall-clock execution time.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


class MetricsCollector:
    """Collects and computes evaluation metrics for a single PLN derivation run."""

    def __init__(self, depth: int, n_distractors: int, guided: bool):
        self.depth = depth
        self.n_distractors = n_distractors
        self.guided = guided

        self.steps_taken: int = 0
        self.rules_fired: int = 0
        self.rules_on_proof_path: int = 0
        self.distractor_selections: int = 0
        self.off_path_selections: int = 0

        self.goal_reached: bool = False
        self.final_stv: Optional[Tuple[float, float]] = None
        self.evidence_stamp: Optional[List[str]] = None

        self.wall_clock_seconds: Optional[float] = None
        self.selected_history: List[Dict[str, Any]] = []
        self.domain_type: str = "transitive_chain"
        self.solution_path: Optional[str] = None
        self.conjunction_verified: Optional[bool] = None

    @property
    def waste_ratio(self) -> float:
        """
        Waste Ratio = 1.0 - (rules_on_proof_path / rules_fired)
        Fraction of selected/fired rules that did not contribute to the target proof.
        """
        if self.rules_fired == 0:
            return 0.0
        return max(0.0, 1.0 - (self.rules_on_proof_path / self.rules_fired))

    def record_selection(
        self,
        statement: str,
        stv: Tuple[float, float],
        evidence: List[str],
        is_on_proof_path: bool,
        is_distractor: bool,
    ) -> None:
        self.steps_taken += 1
        self.rules_fired += 1
        if is_on_proof_path:
            self.rules_on_proof_path += 1
        else:
            self.off_path_selections += 1

        if is_distractor:
            self.distractor_selections += 1

        self.selected_history.append(
            {
                "step": self.steps_taken,
                "statement": statement,
                "stv": stv,
                "evidence": evidence,
                "on_proof_path": is_on_proof_path,
                "is_distractor": is_distractor,
            }
        )

    def summary(self) -> Dict[str, Any]:
        """Return a serializable dictionary summarizing the run."""
        res: Dict[str, Any] = {
            "domain_type": self.domain_type,
            "depth": self.depth,
            "n_distractors": self.n_distractors,
            "guided": self.guided,
            "goal_reached": self.goal_reached,
            "steps_taken": self.steps_taken,
            "rules_fired": self.rules_fired,
            "rules_on_proof_path": self.rules_on_proof_path,
            "off_path_selections": self.off_path_selections,
            "distractor_selections": self.distractor_selections,
            "waste_ratio": round(self.waste_ratio, 4),
            "waste_ratio_pct": f"{self.waste_ratio:.2%}",
            "wall_clock_seconds": (
                round(self.wall_clock_seconds, 4)
                if self.wall_clock_seconds is not None
                else None
            ),
            "final_stv": self.final_stv,
            "evidence_stamp": self.evidence_stamp,
        }
        if self.solution_path is not None:
            res["solution_path"] = self.solution_path
        if self.conjunction_verified is not None:
            res["conjunction_verified"] = self.conjunction_verified
        return res


def _extract_atoms(expr: str) -> List[str]:
    """Extract word tokens from an S-expression string."""
    return re.findall(r"[A-Za-z0-9_\-]+", expr)


def is_step_on_proof_path(
    statement_str: str, proof_nodes: List[str], target_start: str, target_end: str
) -> Tuple[bool, bool]:
    """
    Classify whether a selected sentence statement is on the optimal proof path.

    Returns
    -------
    (is_on_proof_path, is_distractor)
    """
    tokens = _extract_atoms(statement_str)

    # Check if any token is a distractor (starts with 'D' followed by digits)
    has_distractor = any(re.match(r"^D\d+$", t) for t in tokens)
    if has_distractor:
        return False, True

    # For transitive chain: Inheritance X Y
    # On-path if X and Y are both in proof_nodes and node_index(X) < node_index(Y)
    match = re.search(r"Inheritance\s+([A-Za-z0-9_\-]+)\s+([A-Za-z0-9_\-]+)", statement_str)
    if match:
        sub, obj = match.group(1), match.group(2)
        if sub in proof_nodes and obj in proof_nodes:
            idx_sub = proof_nodes.index(sub)
            idx_obj = proof_nodes.index(obj)
            # Forward transitive progression along the chain
            if idx_sub < idx_obj:
                return True, False

    return False, False


def parse_selected_log(
    output_text: str,
    spec: Dict[str, Any],
    guided: bool,
    wall_clock_s: Optional[float] = None,
) -> MetricsCollector:
    """
    Parse the stdout/stderr from PeTTa running a transitive chain benchmark.
    """
    domain_type = spec.get("domain_type", "transitive_chain")
    depth = spec.get("depth", spec.get("depth_short", spec.get("depth_left", 0)))
    collector = MetricsCollector(
        depth=depth,
        n_distractors=len(spec.get("distractor_facts", [])),
        guided=guided,
    )
    collector.domain_type = domain_type
    collector.wall_clock_seconds = wall_clock_s

    proof_nodes = spec.get("nodes", [])
    start_node = spec.get("start_node", "A")
    end_node = spec.get("end_node", spec.get("goal_node", "Z"))

    # 1. Parse all SELECTED lines
    # Format: (SELECTED (Sentence (<stmt>) (stv <s> <c>)) (<ev>)))
    # or variations in whitespace/parens
    selected_pattern = re.compile(
        r"\(SELECTED\s+\(Sentence\s+\((.+?)\s+\(stv\s+([\d\.\-eE]+)\s+([\d\.\-eE]+)\)\)\s+\((.*?)\)\)\)"
    )

    for match in selected_pattern.finditer(output_text):
        stmt = match.group(1).strip()
        s_val = float(match.group(2))
        c_val = float(match.group(3))
        ev_str = match.group(4).strip()
        evidence = ev_str.split() if ev_str else []

        on_path, is_distractor = is_step_on_proof_path(
            stmt, proof_nodes, start_node, end_node
        )
        collector.record_selection(
            stmt, (s_val, c_val), evidence, on_path, is_distractor
        )

    # 2. Parse BENCHMARK_RESULT
    # Format: (BENCHMARK_RESULT: ((stv <s> <c>) (<ev>)))
    result_pattern = re.compile(
        r"\(BENCHMARK_RESULT:\s+\(\(stv\s+([\d\.\-eE]+)\s+([\d\.\-eE]+)\)\s+\((.*?)\)\)\)"
    )
    res_match = result_pattern.search(output_text)
    if res_match:
        collector.goal_reached = True
        s_res = float(res_match.group(1))
        c_res = float(res_match.group(2))
        ev_res = res_match.group(3).strip().split()
        collector.final_stv = (s_res, c_res)
        collector.evidence_stamp = ev_res

        if domain_type == "diamond_dag":
            from prism.benchmarks.domains.multipath_dag import classify_diamond_solution

            collector.solution_path = classify_diamond_solution(ev_res, spec)
        elif domain_type == "tree_conjunction":
            from prism.benchmarks.domains.tree_dag import (
                verify_tree_conjunction_solution,
            )

            collector.conjunction_verified = verify_tree_conjunction_solution(
                ev_res, spec
            )
    else:
        # Check if result was empty ()
        collector.goal_reached = False

    return collector
