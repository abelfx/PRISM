"""Effectful, one-turn OpenPsi ping-pong execution regression."""

from benchmarks.evaluate_openpsi_action_execution import evaluate


def test_real_pingpong_action_outcomes_match_native_v2() -> None:
    result = evaluate()
    for mode in ("native_v2", "prism"):
        healthy = result[mode]["healthy"]
        tired = result[mode]["tired"]
        assert healthy["plan"] == "(act-ping)"
        assert healthy["task_completed"] is True
        assert healthy["motivation_after"] == 0.8
        assert tired["plan"] == "(act-ping)"
        assert tired["task_completed"] is False
        assert tired["ball_lost"] == 1.0
