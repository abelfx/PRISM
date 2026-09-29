"""Validated proof-trace loading and leakage-safe Week 11 dataset splits."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Iterable, List, Sequence, Tuple

from prism.tier1.heuristic_v1 import extract_atoms


@dataclass(frozen=True)
class TraceExample:
    """One candidate/goal/outcome example from a finalized search trace."""

    candidate: str
    goal: str
    strength: float
    confidence: float
    depth: int
    candidate_pool_size: int
    queue_position: int
    outcome: int
    run_id: str
    step: int
    heuristic_score: float

    @property
    def candidate_tokens(self) -> Tuple[str, ...]:
        return tuple(sorted(extract_atoms(self.candidate)))

    @property
    def goal_tokens(self) -> Tuple[str, ...]:
        return tuple(sorted(extract_atoms(self.goal)))

    @property
    def numeric_features(self) -> Tuple[float, float, float, float]:
        pool = max(1, self.candidate_pool_size)
        return (
            min(1.0, max(0.0, self.strength)),
            min(1.0, max(0.0, self.confidence)),
            min(1.0, max(0.0, self.depth / 16.0)),
            min(1.0, max(0.0, self.queue_position / max(1, pool - 1))),
        )


def _as_example(record: dict, source: Path, line_no: int) -> TraceExample:
    required = {"statement", "goal", "on_proof_path", "domain_name", "step"}
    missing = sorted(required - record.keys())
    if missing:
        raise ValueError(f"{source}:{line_no}: missing fields: {', '.join(missing)}")
    if record["on_proof_path"] is None:
        raise ValueError(f"{source}:{line_no}: trace was not finalized")
    pool = int(record.get("candidate_pool_size", 1))
    rank = int(record.get("queue_position", 0))
    if pool < 1 or rank < 0 or rank >= pool:
        raise ValueError(f"{source}:{line_no}: invalid pool/rank {pool}/{rank}")
    return TraceExample(
        candidate=str(record["statement"]),
        goal=str(record["goal"]),
        strength=float(record.get("strength", 1.0)),
        confidence=float(record.get("confidence", 0.5)),
        depth=max(0, int(record.get("depth", 0))),
        candidate_pool_size=pool,
        queue_position=rank,
        outcome=int(bool(record["on_proof_path"])),
        run_id=str(record["domain_name"]),
        step=int(record["step"]),
        heuristic_score=float(record.get("heuristic_score", 0.0)),
    )


def load_trace_jsonl(paths: Iterable[str | Path]) -> List[TraceExample]:
    """Load finalized JSONL traces, rejecting malformed training metadata."""
    examples: List[TraceExample] = []
    for raw_path in paths:
        path = Path(raw_path)
        with path.open("r", encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                if line.strip():
                    examples.append(_as_example(json.loads(line), path, line_no))
    if not examples:
        raise ValueError("no trace examples were loaded")
    return examples


def split_by_run(
    examples: Sequence[TraceExample],
    validation_fraction: float = 0.2,
    seed: int = 42,
) -> Tuple[List[TraceExample], List[TraceExample]]:
    """Split whole search runs so candidates from one run cannot leak across sets."""
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between 0 and 1")
    run_ids = sorted({item.run_id for item in examples})
    if len(run_ids) < 2:
        raise ValueError("at least two distinct trace runs are required")
    random.Random(seed).shuffle(run_ids)
    validation_count = max(1, min(len(run_ids) - 1, round(len(run_ids) * validation_fraction)))
    validation_ids = set(run_ids[:validation_count])
    train = [item for item in examples if item.run_id not in validation_ids]
    validation = [item for item in examples if item.run_id in validation_ids]
    if not {item.outcome for item in train} == {0, 1}:
        raise ValueError("training split must contain positive and negative outcomes")
    return train, validation
