"""
Unit tests for PRISM Proof Trace Logger.
Verifies step feature extraction, retroactive proof attribution,
and JSONL dataset export.
"""

import json
import os
import tempfile

from prism.benchmarks.utils.trace_logger import ProofStepTrace, ProofTraceSession


def test_trace_record_step_feature_extraction():
    """Verify that record_step correctly computes overlap, depth, and scores."""
    goal = ["Inheritance", "A", "Z"]
    session = ProofTraceSession("test_domain", goal)

    step1 = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.85]], [1]]
    trace = session.record_step(1, step1, candidate_pool_size=5)

    assert isinstance(trace, ProofStepTrace)
    assert trace.step == 1
    assert trace.confidence == 0.85
    assert trace.depth == 0  # stamp [1] has len 1 -> depth 0
    assert trace.evidence_stamp == ["1"]
    assert trace.atom_overlap > 0.0  # shares 'A' with goal
    assert trace.heuristic_score > 0.0
    assert trace.on_proof_path is None  # not finalized yet


def test_trace_session_retroactive_attribution():
    """Verify that finalize attributes steps correctly based on final proof stamp."""
    goal = ["Inheritance", "A", "Z"]
    session = ProofTraceSession("test_domain", goal)

    # Step 1: On-path premise (stamp [1])
    s1 = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], [1]]
    session.record_step(1, s1)

    # Step 2: Off-path distractor (stamp [200])
    s2 = ["Sentence", [["Inheritance", "D1", "D2"], ["stv", 0.9, 0.9]], [200]]
    session.record_step(2, s2)

    # Step 3: Derived lemma on path (stamp [1, 2])
    s3 = ["Sentence", [["Inheritance", "A", "C"], ["stv", 0.8, 0.7]], [1, 2]]
    session.record_step(3, s3)

    # Final goal was derived with evidence stamp ['1', '2']
    session.finalize(final_evidence_stamp=["1", "2"])

    assert session.goal_reached is True
    # Step 1 stamp {1} is subset of {1, 2} -> on path
    assert session.steps[0].on_proof_path is True
    # Step 2 stamp {200} is NOT subset of {1, 2} -> off path
    assert session.steps[1].on_proof_path is False
    # Step 3 stamp {1, 2} is subset of {1, 2} -> on path
    assert session.steps[2].on_proof_path is True

    summary = session.to_dict()
    assert summary["total_steps"] == 3
    assert summary["on_path_steps"] == 2


def test_trace_session_unreached_goal():
    """Verify that if goal was not reached, all steps are labeled false."""
    session = ProofTraceSession("test_domain", ["Goal"])
    s1 = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], [1]]
    session.record_step(1, s1)

    session.finalize(final_evidence_stamp=None)
    assert session.goal_reached is False
    assert session.steps[0].on_proof_path is False


def test_trace_export_jsonl():
    """Verify that export_jsonl produces valid JSON records."""
    session = ProofTraceSession("test_domain", ["Inheritance", "A", "Z"])
    s1 = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], [1]]
    session.record_step(1, s1)
    session.finalize(["1"])

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        filepath = tf.name

    try:
        out_path = session.export_jsonl(filepath)
        assert os.path.exists(out_path)

        with open(out_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["step"] == 1
        assert record["on_proof_path"] is True
        assert record["domain_name"] == "test_domain"
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
