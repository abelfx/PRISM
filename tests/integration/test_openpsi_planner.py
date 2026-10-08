"""Assert actual PeTTa-OpenPSI behavior, not PeTTa's top-level 'true' status."""

import os
from pathlib import Path
import re
import subprocess


def test_live_openpsi_action_control():
    workspace = Path(__file__).resolve().parents[3]
    prism_src = workspace / "prism" / "src"
    script = workspace / "prism" / "tests" / "integration" / "test_openpsi_planner.metta"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(prism_src) + os.pathsep + env.get("PYTHONPATH", "")
    run = subprocess.run(
        ["sh", "run.sh", str(script)],
        cwd=workspace / "PeTTa",
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", run.stdout + run.stderr)
    lines = set(output.splitlines())
    assert run.returncode == 0, output[-3000:]
    assert "(OPENPSI_NATIVE_PICK (0.0 (idle deadend)))" in lines, output[-3000:]
    assert "(PRISM_OPENPSI_PICK (explore middle))" in lines, output[-3000:]
    assert "PRISM_OPENPSI_PASS" in lines, output[-3000:]
    assert "PRISM_OPENPSI_BUDGET_PASS" in lines, output[-3000:]
    assert "PRISM_OPENPSI_FALLBACK_PASS" in lines, output[-3000:]
    assert "PRISM_OPENPSI_FAIL" not in lines, output[-3000:]
    assert "PRISM_OPENPSI_BUDGET_FAIL" not in lines, output[-3000:]
    assert "PRISM_OPENPSI_FALLBACK_FAIL" not in lines, output[-3000:]


def test_openpsi_feedback_loop_dispatch():
    workspace = Path(__file__).resolve().parents[3]
    script = (
        workspace
        / "other_hyperon"
        / "PeTTa-OpenPSI"
        / "main"
        / "feedback-loop"
        / "prism-feedback-test.metta"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace / "prism" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    run = subprocess.run(
        ["sh", "run.sh", str(script)],
        cwd=workspace / "PeTTa",
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", run.stdout + run.stderr)
    lines = set(output.splitlines())
    assert run.returncode == 0, output[-3000:]
    assert "PRISM_OPENPSI_FEEDBACK_DISPATCH_PASS" in lines, output[-3000:]
    assert "PRISM_OPENPSI_FEEDBACK_DISPATCH_FAIL" not in lines, output[-3000:]


def test_original_feedback_loop_without_prism():
    workspace = Path(__file__).resolve().parents[3]
    script = (
        workspace
        / "other_hyperon"
        / "PeTTa-OpenPSI"
        / "main"
        / "feedback-loop"
        / "native-feedback-test.metta"
    )
    run = subprocess.run(
        ["sh", "run.sh", str(script)],
        cwd=workspace / "PeTTa",
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", run.stdout + run.stderr)
    lines = set(output.splitlines())
    assert run.returncode == 0, output[-3000:]
    assert "OPENPSI_NATIVE_COMPAT_PASS" in lines, output[-3000:]
    assert "OPENPSI_NATIVE_COMPAT_FAIL" not in lines, output[-3000:]


def test_path_valid_feedback_loop_updates_demand_only_for_valid_route():
    from benchmarks.evaluate_openpsi_full_cycle import evaluate

    result = evaluate()
    native = result["native"]
    prism = result["prism"]
    assert native["plan"] == "(idle finish)"
    assert native["plan_replays_to_goal"] is False
    assert native["loop_reported_goal_met"] is False
    assert native["demand_after"] == "(demand competence 0.3 0.5 0.1)"
    assert native["second_demand_after"] == "(demand competence 0.3 0.5 0.1)"
    assert native["second_updated_demand"] is None
    assert prism["plan"] == "(explore finish)"
    assert prism["plan_replays_to_goal"] is True
    assert prism["loop_reported_goal_met"] is True
    assert prism["demand_after"] == "(demand competence 0.3 0.5 0.55)"
    assert prism["second_updated_demand"] in {"competence", "affiliation", "energy"}
    assert "(demand competence 0.3 0.5 0.1)" not in prism["kb_demands_after"]
    assert "(demand competence 0.3 0.5 0.1)" not in prism["second_kb_demands_after"]
    assert prism["emotion_output"] != native["emotion_output"]


def test_repository_pingpong_rule_shape_and_unreachable_fallback():
    workspace = Path(__file__).resolve().parents[3]
    script = workspace / "prism" / "benchmarks" / "evaluate_openpsi_pingpong.metta"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace / "prism" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    run = subprocess.run(
        ["sh", "run.sh", str(script)], cwd=workspace / "PeTTa", env=env,
        text=True, capture_output=True, timeout=20, check=False,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", run.stdout + run.stderr)
    assert run.returncode == 0, output[-3000:]
    assert "(PINGPONG_RESULT (act-ping) ((act-ping (ball heading-to-opponent))) (act-ping (ball heading-to-opponent)) (act-ping (ball heading-to-opponent)))" in output.splitlines()
    assert "(PINGPONG_UNREACHABLE (act-ping (ball heading-to-opponent)) (act-ping (ball heading-to-opponent)))" in output.splitlines()


def test_repository_conversation_rules_drive_valid_feedback_update():
    from benchmarks.evaluate_openpsi_full_cycle import evaluate

    result = evaluate("conversation")
    assert result["native"]["plan_replays_to_goal"] is False
    assert result["native"]["demand_after"] == "(demand competence 0.3 0.5 0.1)"
    assert result["prism"]["plan_replays_to_goal"] is True
    assert result["prism"]["demand_after"] == "(demand competence 0.3 0.5 0.55)"
    assert "(demand competence 0.3 0.5 0.1)" not in result["prism"]["kb_demands_after"]
    assert result["prism"]["emotion_output"] != result["native"]["emotion_output"]


def test_fresh_process_planner_comparison_replays_returned_plans():
    from benchmarks.evaluate_openpsi_fresh import evaluate

    result = evaluate(("Send-Greeting",))
    assert result["totals"]["V1"]["invalid"] == 1
    assert result["totals"]["V2"]["solved"] == 1
    assert result["totals"]["PRISM"]["solved"] == 1
    assert all(item["cold"]["outcome"] == item["warm"]["outcome"]
               for item in result["observations"])


def test_trader_schema_is_not_silently_counted_as_supported():
    workspace = Path(__file__).resolve().parents[3]
    script = workspace / "prism" / "benchmarks" / "evaluate_openpsi_trader_schema.metta"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace / "prism" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    run = subprocess.run(
        ["sh", "run.sh", str(script)], cwd=workspace / "PeTTa", env=env,
        text=True, capture_output=True, timeout=20, check=False,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", run.stdout + run.stderr)
    assert run.returncode == 0, output[-3000:]
    assert "(TRADER_SCHEMA_RESULT 24 () () ())" in output.splitlines()
