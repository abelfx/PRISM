from pathlib import Path

from benchmarks.domains.kg_similarity import (
    concept_stvs,
    held_out_queries,
    load_similarity_kg,
    select_bipartite_slice,
    to_pln_sentences,
)
from prism.adapters.petta.runtime import apply_pln_sentences


KG_PATH = Path(__file__).resolve().parents[3] / "kgadexp.metta"


def test_sample_inventory_and_malformed_source_detection():
    kg = load_similarity_kg(KG_PATH)
    assert kg.raw_edge_count == 8280
    assert len(kg.unique_edges) == 3930
    assert kg.duplicate_count == 4350
    assert len(kg.nodes) == 161
    assert not kg.is_source_syntax_balanced
    assert kg.parenthesis_balance == -1


def test_slice_converts_to_symmetric_pln_sentences_with_shared_evidence():
    kg = load_similarity_kg(KG_PATH)
    sources, targets, edges = select_bipartite_slice(kg, source_limit=3, target_limit=4)
    assert len(edges) == 12
    sentences = to_pln_sentences(edges)
    assert len(sentences) == 24
    assert sentences[0][2] == sentences[1][2]
    assert sentences[0][1][0][1:] == list(reversed(sentences[1][1][0][1:]))
    assert len(concept_stvs((*sources, *targets))) == 7
    assert len(held_out_queries(sources, limit=3)) == 3


def test_similarity_slice_uses_live_pln_apply():
    kg = load_similarity_kg(KG_PATH)
    sources, targets, edges = select_bipartite_slice(kg, source_limit=3, target_limit=4)
    sentences = to_pln_sentences(edges)
    left, right, bridge = sources[0], sources[1], targets[0]
    first = next(s for s in sentences if s[1][0] == ["Similarity", left, bridge])
    second = next(s for s in sentences if s[1][0] == ["Similarity", bridge, right])
    result = apply_pln_sentences(first, second, concept_stvs((*sources, *targets)))
    assert result is not None
    assert result[1][0] == ["Similarity", left, right]
    assert result[2] == [first[2][0], second[2][0]]
