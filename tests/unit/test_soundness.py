"""Week 10 independent proof replay tests."""

from prism.adapters.petta.runtime import apply_pln_sentences
from prism.search.rules import parse_sentence
from prism.verification import verify_proof


def sentence(subject, object_node, stamp, strength=0.9, confidence=0.8):
    return [
        "Sentence",
        [["Inheritance", subject, object_node], ["stv", strength, confidence]],
        list(stamp),
    ]


def deterministic_kernel(left, right, _stvs=None):
    p1, p2 = parse_sentence(left), parse_sentence(right)
    if p1 and p2 and p1.object_node == p2.subject and set(p1.evidence_stamp).isdisjoint(p2.evidence_stamp):
        return sentence(p1.subject, p2.object_node, p1.evidence_stamp + p2.evidence_stamp, 0.7, 0.6)
    if p1 and p2 and p2.object_node == p1.subject and set(p1.evidence_stamp).isdisjoint(p2.evidence_stamp):
        return sentence(p2.subject, p1.object_node, p2.evidence_stamp + p1.evidence_stamp, 0.7, 0.6)
    return None


def test_replays_complete_proof_independently():
    facts = [sentence("A", "B", ["1"]), sentence("B", "C", ["2"])]
    action = sentence("A", "C", ["1", "2"], 0.7, 0.6)
    result = verify_proof(facts, [action], ["Inheritance", "A", "C"], apply_fn=deterministic_kernel)
    assert result.valid
    assert result.steps_replayed == 1
    assert result.goal_valid


def test_rejects_injected_or_unknown_evidence():
    facts = [sentence("A", "B", ["1"]), sentence("B", "C", ["2"])]
    injected = sentence("A", "C", ["1", "9"], 0.7, 0.6)
    result = verify_proof(facts, [injected], ["Inheritance", "A", "C"], apply_fn=deterministic_kernel)
    assert not result.valid
    assert result.first_failure.code == "unknown_evidence"


def test_rejects_stv_and_circular_evidence_mismatches():
    facts = [sentence("A", "B", ["1"]), sentence("B", "C", ["2"])]
    wrong_stv = sentence("A", "C", ["1", "2"], 0.71, 0.6)
    mismatch = verify_proof(facts, [wrong_stv], ["Inheritance", "A", "C"], apply_fn=deterministic_kernel)
    assert mismatch.first_failure.code == "stv_mismatch"

    circular = sentence("A", "C", ["1", "1"], 0.7, 0.6)
    overlap = verify_proof(facts, [circular], ["Inheritance", "A", "C"], apply_fn=deterministic_kernel)
    assert overlap.first_failure.code == "circular_evidence"


def test_kernel_exception_fails_closed():
    facts = [sentence("A", "B", ["1"]), sentence("B", "C", ["2"])]

    def broken_kernel(*_args):
        raise RuntimeError("kernel unavailable")

    result = verify_proof(
        facts,
        [sentence("A", "C", ["1", "2"], 0.7, 0.6)],
        ["Inheritance", "A", "C"],
        apply_fn=broken_kernel,
    )
    assert not result.valid
    assert result.first_failure.code == "kernel_error"
    assert result.steps_replayed == 0


def test_rejects_incomplete_and_unsupported_paths():
    facts = [sentence("A", "B", ["1"]), sentence("B", "C", ["2"])]
    incomplete = verify_proof(facts, [], ["Inheritance", "A", "C"], apply_fn=deterministic_kernel)
    assert incomplete.first_failure.code == "goal_not_proved"

    injected = sentence("A", "C", ["1", "2"], 0.7, 0.6)
    unsupported = verify_proof(
        facts,
        [injected],
        ["Inheritance", "A", "C"],
        apply_fn=lambda *_: None,
    )
    assert unsupported.first_failure.code == "unsupported_action"


def test_rejects_erased_or_extra_support():
    facts = [
        sentence("A", "B", ["1"]),
        sentence("B", "C", ["2"]),
        sentence("X", "Y", ["3"]),
    ]
    erased = sentence("A", "C", ["1"], 0.7, 0.6)
    result = verify_proof(facts, [erased], ["Inheritance", "A", "C"], apply_fn=deterministic_kernel)
    assert not result.valid
    assert result.first_failure.code in {"unsupported_action", "evidence_mismatch"}


def test_real_pln_replay_matches_term_stv_and_evidence():
    facts = [sentence("A", "B", ["1"]), sentence("B", "C", ["2"])]
    stvs = {"A": (1 / 3, 0.9), "B": (1 / 3, 0.9), "C": (1 / 3, 0.9)}
    derived = apply_pln_sentences(facts[0], facts[1], stvs)
    result = verify_proof(facts, [derived], ["Inheritance", "A", "C"], concept_stvs=stvs)
    assert result.valid
    assert result.term_match and result.stv_match and result.evidence_match
