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
