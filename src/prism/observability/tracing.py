"""
Structured Proof Trace Logger & Dataset Builder for PRISM.

Instruments inference derivation steps, records state-action-goal transitions,
and retroactively labels steps with ground-truth proof path attribution
for downstream best-first search (Weeks 5-6) and neural model training (Week 11).
"""

from dataclasses import asdict, dataclass, field
import json
import os
import re
from typing import Any, Dict, List, Optional, Set

from prism.core.config import DEFAULT_CONFIG, Tier1Config
from prism.tier1.heuristic_v1 import (
    compute_depth_discount,
    compute_overlap,
    compute_v1_score,
    extract_atoms,
    extract_confidence,
    extract_depth,
)


@dataclass
class ProofStepTrace:
    """
    Representation of a single logged inference task selection step.

    Attributes
    ----------
    step : int
        Derivation step sequence number (1-indexed).
    statement : str
        String representation of the selected sentence's relational statement.
    strength : float
        Truth value strength.
    confidence : float
        Truth value confidence.
    evidence_stamp : List[str]
        Evidence stamp IDs associated with this sentence.
    goal : str
        String representation of the active query goal.
    candidate_pool_size : int
        Size of the active task frontier at the time of selection.
    depth : int
        Derivation depth inferred from the evidence stamp length.
    atom_overlap : float
        Symbolic token overlap with the target goal.
    depth_discount : float
        Geometric depth decay penalty factor.
    heuristic_score : float
        Calculated Tier 1 v1 score.
    on_proof_path : Optional[bool]
        True if this step's evidence stamp is a subset of the final goal's proof stamp.
        None prior to session finalization.
    """

    step: int
    statement: str
    strength: float
    confidence: float
    evidence_stamp: List[str]
    goal: str
    candidate_pool_size: int = 1
    depth: int = 0
    atom_overlap: float = 0.0
    depth_discount: float = 0.0
    heuristic_score: float = 0.0
    on_proof_path: Optional[bool] = None


class ProofTraceSession:
    """
    Records inference traces across a derivation session and performs retroactive labeling.

    Explicit Non-Goals
    ------------------
    - Does not alter derivation execution or priority queue ranking.
    - Does not compute PLN truth values or fire inference rules.
    """

    def __init__(
        self,
        domain_name: str,
        goal_expr: Any,
        config: Optional[Tier1Config] = None,
    ) -> None:
        self.domain_name = domain_name
        self.goal_expr = goal_expr
        self.goal_str = str(goal_expr)
        self.goal_atoms = extract_atoms(goal_expr)
        self.config = config or DEFAULT_CONFIG.tier1

        self.steps: List[ProofStepTrace] = []
        self.goal_reached: bool = False
        self.final_stamp: Optional[Set[str]] = None

    def record_step(
        self,
        step: int,
        sentence_expr: Any,
        candidate_pool_size: int = 1,
    ) -> ProofStepTrace:
        """
        Record a single task selection step and compute its feature vector.

        Parameters
        ----------
        step : int
            Step counter.
        sentence_expr : Any
            Sentence S-expression (e.g. ['Sentence', [['Inheritance', 'A', 'B'], ['stv', s, c]], [1]]).
        candidate_pool_size : int
            Number of eligible tasks in the queue.

        Returns
        -------
        ProofStepTrace
            The recorded step trace dataclass.
        """
        conf = extract_confidence(sentence_expr, self.config.default_confidence)
        depth = extract_depth(sentence_expr)
        sent_atoms = extract_atoms(sentence_expr)
        overlap = compute_overlap(sent_atoms, self.goal_atoms)
        depth_disc = compute_depth_discount(depth, self.config.delta, self.config.gamma)
        score = compute_v1_score(sentence_expr, self.goal_expr, self.config)

        # Extract statement and strength
        statement_str = ""
        strength = 1.0
        stamp: List[str] = []

        if isinstance(sentence_expr, (list, tuple)) and len(sentence_expr) >= 2:
            body = sentence_expr[1]
            if isinstance(body, (list, tuple)) and len(body) >= 2:
                statement_str = str(body[0])
                stv = body[1]
                if isinstance(stv, (list, tuple)) and len(stv) >= 2:
                    try:
                        strength = float(stv[1])
                    except (ValueError, TypeError, IndexError):
                        strength = 1.0

            if len(sentence_expr) >= 3:
                raw_stamp = sentence_expr[2]
                if isinstance(raw_stamp, (list, tuple)):
                    stamp = [str(e) for e in raw_stamp]
        elif isinstance(sentence_expr, str):
            match_body = re.search(
                r"\(Sentence\s+\((.+?)\s+\(stv\s+([\d\.\-eE]+)\s+[\d\.\-eE]+\)\)\s+\((.*?)\)\)",
                sentence_expr,
            )
            if match_body:
                statement_str = match_body.group(1).strip()
                try:
                    strength = float(match_body.group(2))
                except (ValueError, TypeError):
                    strength = 1.0
                ev_str = match_body.group(3).strip()
                stamp = ev_str.split() if ev_str else []
            else:
                ev_match = re.search(r"\)\s+\((.*?)\)\s*\)", sentence_expr)
                if ev_match:
                    stamp = ev_match.group(1).strip().split()

        trace = ProofStepTrace(
            step=step,
            statement=statement_str or str(sentence_expr),
            strength=strength,
            confidence=conf,
            evidence_stamp=stamp,
            goal=self.goal_str,
            candidate_pool_size=candidate_pool_size,
            depth=depth,
            atom_overlap=round(overlap, 4),
            depth_discount=round(depth_disc, 4),
            heuristic_score=round(score, 4),
            on_proof_path=None,
        )
        self.steps.append(trace)
        return trace

    def finalize(self, final_evidence_stamp: Optional[List[str]]) -> None:
        """
        Retroactively attribute each recorded step as on-proof-path or off-proof-path.

        Parameters
        ----------
        final_evidence_stamp : Optional[List[str]]
            The evidence stamp of the final derived sentence that satisfied the goal.
        """
        if final_evidence_stamp is not None and len(final_evidence_stamp) > 0:
            self.goal_reached = True
            self.final_stamp = set(str(e) for e in final_evidence_stamp)
            for trace in self.steps:
                step_stamp = set(trace.evidence_stamp)
                if step_stamp and step_stamp.issubset(self.final_stamp):
                    trace.on_proof_path = True
                else:
                    trace.on_proof_path = False
        else:
            self.goal_reached = False
            self.final_stamp = None
            for trace in self.steps:
                trace.on_proof_path = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert session and all step traces to a serializable dictionary."""
        return {
            "domain_name": self.domain_name,
            "goal": self.goal_str,
            "goal_reached": self.goal_reached,
            "final_stamp": list(self.final_stamp) if self.final_stamp else None,
            "total_steps": len(self.steps),
            "on_path_steps": sum(1 for s in self.steps if s.on_proof_path is True),
            "steps": [asdict(s) for s in self.steps],
        }

    def export_jsonl(self, output_filepath: str) -> str:
        """
        Append every recorded step as an independent JSON Lines record.

        Parameters
        ----------
        output_filepath : str
            Target .jsonl file path.

        Returns
        -------
        str
            The absolute path of the written file.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
        with open(output_filepath, "a", encoding="utf-8") as f:
            for trace in self.steps:
                record = asdict(trace)
                record["domain_name"] = self.domain_name
                record["goal_reached"] = self.goal_reached
                f.write(json.dumps(record) + "\n")
        return output_filepath
