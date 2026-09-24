"""Streaming normalization for the external MeTTa knowledge-graph exports.

The raw exports are never evaluated or modified.  This module extracts only
binary relations named by the caller, deduplicates them, and records enough
provenance to make a benchmark slice reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple


_ATOM = r"(?:'[^'\n]*'|[^\s()]+)"
_EDGE_RE = re.compile(
    rf"\((?P<relation>{_ATOM})\s+(?P<left>{_ATOM})\s+(?P<right>{_ATOM})\)"
)
_TV_RE = re.compile(
    r"\(\s*'?([0-9]*\.?[0-9]+)'?\s+'?([0-9]*\.?[0-9]+)'?\s*\)"
)
_PLN_SAFE_ATOM_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _atom(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


@dataclass(frozen=True)
class ExternalKG:
    source_path: str
    source_sha256: str
    relation: str
    raw_relation_edges: int
    duplicate_edges: int
    self_loops: int
    unsupported_compound_lines: int
    edges: Tuple[Tuple[str, str], ...]
    source_tv_counts: Tuple[Tuple[Tuple[float, float], int], ...]
    missing_tv_count: int

    @property
    def unique_edges(self) -> int:
        return len(self.edges)


def source_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_relation(path: str | Path, relation: str = "isa") -> ExternalKG:
    """Stream one binary relation from flat or adjacency-style MeTTa."""
    source = Path(path)
    unique: set[Tuple[str, str]] = set()
    raw_count = 0
    duplicates = 0
    self_loops = 0
    unsupported_compounds = 0
    missing_tvs = 0
    tv_counts: Dict[Tuple[float, float], int] = {}

    with source.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            saw_open = "(" in line
            matches = list(_EDGE_RE.finditer(line))
            if saw_open and not matches:
                # Unary declarations are valid input, not malformed edges.
                stripped = line.strip()
                if stripped.startswith("(("):
                    unsupported_compounds += 1
                continue
            for match in matches:
                if _atom(match.group("relation")).lower() != relation.lower():
                    continue
                left = _atom(match.group("left"))
                right = _atom(match.group("right"))
                raw_count += 1
                if left == right:
                    self_loops += 1
                    continue
                edge = (left, right)
                if edge in unique:
                    duplicates += 1
                    continue
                unique.add(edge)
                suffix = line[match.end() :]
                tv_match = _TV_RE.search(suffix)
                if tv_match:
                    tv = (float(tv_match.group(1)), float(tv_match.group(2)))
                    tv_counts[tv] = tv_counts.get(tv, 0) + 1
                else:
                    missing_tvs += 1

    if not unique:
        raise ValueError(f"No non-self {relation!r} edges found in {source}")
    return ExternalKG(
        source_path=str(source.resolve()),
        source_sha256=source_sha256(source),
        relation=relation,
        raw_relation_edges=raw_count,
        duplicate_edges=duplicates,
        self_loops=self_loops,
        unsupported_compound_lines=unsupported_compounds,
        edges=tuple(sorted(unique)),
        source_tv_counts=tuple(sorted(tv_counts.items())),
        missing_tv_count=missing_tvs,
    )


def find_transitive_chain(
    edges: Sequence[Tuple[str, str]], depth: int = 3
) -> Tuple[Tuple[str, str], ...]:
    """Return a deterministic executable chain whose closure is held out.

    Quoted/spaced and numeric-only atoms remain part of the source audit, but
    are excluded from this inference benchmark because PRISM's current MeTTa
    bridge and Stage 0 tokenizer support symbolic atoms only.
    """
    if depth < 2:
        raise ValueError("depth must be at least 2")
    safe_edges = executable_edges(edges)
    edge_set = set(safe_edges)
    outgoing: Dict[str, List[str]] = {}
    for left, right in safe_edges:
        outgoing.setdefault(left, []).append(right)
    for values in outgoing.values():
        values.sort()

    def extend(nodes: List[str]) -> List[str] | None:
        if len(nodes) == depth + 1:
            return nodes if (nodes[0], nodes[-1]) not in edge_set else None
        for target in outgoing.get(nodes[-1], []):
            if target in nodes:
                continue
            result = extend([*nodes, target])
            if result is not None:
                return result
        return None

    for start in sorted(outgoing):
        nodes = extend([start])
        if nodes is not None:
            return tuple(zip(nodes, nodes[1:]))
    raise ValueError(f"No acyclic held-out chain of depth {depth} found")


def executable_edges(
    edges: Iterable[Tuple[str, str]],
) -> Tuple[Tuple[str, str], ...]:
    """Return edges supported by the current Stage 0 and MeTTa bridge."""
    return tuple(
        edge
        for edge in edges
        if all(_PLN_SAFE_ATOM_RE.fullmatch(node) for node in edge)
    )


def progressive_slice(
    kg: ExternalKG,
    size: int,
    proof_edges: Sequence[Tuple[str, str]],
) -> Tuple[Tuple[str, str], ...]:
    """Keep the proof fixed and add deterministic real-source distractors."""
    proof = tuple(proof_edges)
    if size < len(proof):
        raise ValueError("slice size is smaller than the proof")
    selected = list(proof)
    selected_set = set(proof)
    proof_nodes = {node for edge in proof for node in edge}
    # Prefer unrelated facts, making frontier reduction measurable without
    # inventing distractors or altering the source graph.
    ordered = sorted(
        (edge for edge in executable_edges(kg.edges) if edge not in selected_set),
        key=lambda edge: (bool(set(edge) & proof_nodes), edge),
    )
    selected.extend(ordered[: size - len(selected)])
    if len(selected) != size:
        raise ValueError(
            f"Requested {size} edges but source has only "
            f"{len(executable_edges(kg.edges))} executable edges"
        )
    return tuple(selected)


def to_inheritance_sentences(
    edges: Iterable[Tuple[str, str]],
    strength: float = 0.8,
    confidence: float = 0.9,
) -> List[Any]:
    """Map only source ``isa`` edges to authoritative PLN Inheritance facts."""
    sentences: List[Any] = []
    for left, right in edges:
        digest = hashlib.sha256(f"isa\0{left}\0{right}".encode()).hexdigest()[:16]
        sentences.append(
            [
                "Sentence",
                [["Inheritance", left, right], ["stv", strength, confidence]],
                [f"e{digest}"],
            ]
        )
    return sentences
