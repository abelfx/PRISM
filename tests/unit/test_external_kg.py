from pathlib import Path

from benchmarks.domains.external_kg import (
    find_transitive_chain,
    load_relation,
    progressive_slice,
    to_inheritance_sentences,
)


def test_streaming_loader_handles_flat_and_adjacency_formats(tmp_path: Path):
    source = tmp_path / "mixed.metta"
    source.write_text(
        "((isa a b) ('0.8' '0.9'))\n"
        "(b ((isa b c) (0.8 0.9)) ((isa b c) (0.8 0.9)))\n"
        "(c ((relatedto c d)))\n",
        encoding="utf-8",
    )
    kg = load_relation(source)
    assert kg.edges == (("a", "b"), ("b", "c"))
    assert kg.raw_relation_edges == 3
    assert kg.duplicate_edges == 1
    assert dict(kg.source_tv_counts) == {(0.8, 0.9): 2}


def test_chain_goal_is_held_out_and_slice_uses_real_edges():
    edges = (("1", "number"), ("a", "b"), ("b", "c"), ("c", "d"), ("x", "y"))
    chain = find_transitive_chain(edges, depth=3)
    assert chain == edges[1:4]
    assert (chain[0][0], chain[-1][1]) not in edges

    class KG:
        pass

    kg = KG()
    kg.edges = edges
    sliced = progressive_slice(kg, 4, chain)
    assert set(sliced) == set(edges[1:])
    sentences = to_inheritance_sentences(sliced)
    assert all(sentence[1][0][0] == "Inheritance" for sentence in sentences)
    assert len({sentence[2][0] for sentence in sentences}) == 4
