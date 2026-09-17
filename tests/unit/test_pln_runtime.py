"""Unit tests for live MeTTa PLN.Apply used by PRISM search."""

from prism.search.pln_runtime import (
    apply_pln_pair,
    parse_stv_declarations,
    stamp_disjoint,
)
from prism.search.rules import parse_sentence


def test_stamp_disjoint_skips_overlapping_evidence():
    assert stamp_disjoint(("1",), ("2",)) is True
    assert stamp_disjoint(("1", "2"), ("2", "3")) is False
    assert stamp_disjoint((), ("1",)) is True


def test_parse_stv_declarations():
    table = parse_stv_declarations(["(= (STV A) (stv 0.1667 0.9))"])
    assert table["A"] == (0.1667, 0.9)


def test_pln_apply_inheritance_chain():
    p1 = parse_sentence(["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]])
    p2 = parse_sentence(["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.9]], ["2"]])
    stvs = parse_stv_declarations(
        [
            "(= (STV A) (stv 0.3333 0.9))",
            "(= (STV B) (stv 0.3333 0.9))",
            "(= (STV C) (stv 0.3333 0.9))",
        ]
    )
    result = apply_pln_pair(p1, p2, stvs)
    parsed = parse_sentence(result)
    assert parsed is not None
    assert parsed.subject == "A"
    assert parsed.object_node == "C"
    assert parsed.relation == "Inheritance"
    assert parsed.evidence_stamp == ("1", "2")
    assert parsed.confidence > 0.0
    assert parsed.strength != round(0.9 * 0.9, 4)


def test_pln_apply_rejects_overlapping_stamps():
    p1 = parse_sentence(["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.8]], ["1"]])
    p_circ = parse_sentence(["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.9]], ["1"]])
    stvs = {"A": (1.0 / 3.0, 0.9), "B": (1.0 / 3.0, 0.9), "C": (1.0 / 3.0, 0.9)}
    assert apply_pln_pair(p1, p_circ, stvs) is None
