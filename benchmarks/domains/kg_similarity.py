"""Loader and deterministic pilot-query builder for similarity KG exports.

The source format is an adjacency list such as::

    (ants ((similarityLink abamectin ants) ...))

It is not directly executable PLN.  This module treats ``similarityLink`` as
an undirected source relation, deduplicates it, and emits authoritative PLN
``Sentence`` values with stable evidence IDs.  Both directions are materialized
because ``Similarity`` is symmetric while PLN's binary transitive rule is
orientation-sensitive at the representation level.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


_EDGE_RE = re.compile(
    r"\(similarityLink\s+([^\s()]+)\s+([^\s()]+)\)"
)


@dataclass(frozen=True)
class SimilarityKG:
    source_path: str
    raw_edge_count: int
    duplicate_count: int
    unique_edges: Tuple[Tuple[str, str], ...]
    nodes: Tuple[str, ...]
    parenthesis_balance: int

    @property
    def is_source_syntax_balanced(self) -> bool:
        return self.parenthesis_balance == 0


def load_similarity_kg(path: str | Path) -> SimilarityKG:
    """Parse and deduplicate ``similarityLink`` edges without evaluating input."""
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    raw_edges = _EDGE_RE.findall(text)
    if not raw_edges:
        raise ValueError(f"No similarityLink edges found in {source}")

    unique_edges = tuple(sorted(set(raw_edges)))
    nodes = tuple(sorted({node for edge in unique_edges for node in edge}))
    return SimilarityKG(
        source_path=str(source.resolve()),
        raw_edge_count=len(raw_edges),
        duplicate_count=len(raw_edges) - len(unique_edges),
        unique_edges=unique_edges,
        nodes=nodes,
        parenthesis_balance=text.count("(") - text.count(")"),
    )


def select_bipartite_slice(
    kg: SimilarityKG,
    source_limit: int,
    target_limit: int,
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[Tuple[str, str], ...]]:
    """Select a deterministic dense bipartite slice from an adjacency export."""
    outgoing: Dict[str, set[str]] = {}
    incoming: Dict[str, set[str]] = {}
    for left, right in kg.unique_edges:
        outgoing.setdefault(left, set()).add(right)
        incoming.setdefault(right, set()).add(left)

    sources = tuple(
        node for node, _ in sorted(outgoing.items(), key=lambda item: (-len(item[1]), item[0]))
    )[:source_limit]
    targets = tuple(
        node for node, _ in sorted(incoming.items(), key=lambda item: (-len(item[1]), item[0]))
    )[:target_limit]
    source_set, target_set = set(sources), set(targets)
    edges = tuple(
        (left, right)
        for left, right in kg.unique_edges
        if left in source_set and right in target_set
    )
    if len(sources) < 2 or not targets or not edges:
        raise ValueError("Selected slice cannot produce a two-hop similarity query")
    return sources, targets, edges


def to_pln_sentences(
    edges: Sequence[Tuple[str, str]],
    strength: float = 0.9,
    confidence: float = 0.8,
) -> List[Any]:
    """Materialize both orientations with one stable evidence ID per source edge."""
    sentences: List[Any] = []
    for evidence_id, (left, right) in enumerate(sorted(set(edges)), start=1):
        stamp = [str(evidence_id)]
        sentences.append(
            ["Sentence", [["Similarity", left, right], ["stv", strength, confidence]], stamp]
        )
        sentences.append(
            ["Sentence", [["Similarity", right, left], ["stv", strength, confidence]], stamp]
        )
    return sentences


def concept_stvs(nodes: Iterable[str], confidence: float = 0.9) -> Dict[str, Tuple[float, float]]:
    unique = tuple(sorted(set(nodes)))
    prior = round(1.0 / max(len(unique), 1), 8)
    return {node: (prior, confidence) for node in unique}


def held_out_queries(sources: Sequence[str], limit: int = 5) -> List[List[str]]:
    """Build source-source goals absent from the source bipartite edge set."""
    goals: List[List[str]] = []
    for i, left in enumerate(sources):
        for right in sources[i + 1 :]:
            goals.append(["Similarity", left, right])
            if len(goals) >= limit:
                return goals
    return goals

