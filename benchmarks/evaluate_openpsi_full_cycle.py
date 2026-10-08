"""Noninteractive smoke evaluation of the real PeTTa-OpenPSI feedback loop.

Each selector runs in a fresh PeTTa process against the same three-rule
fixture. The fixture imports the port's normalization module explicitly:
the feedback-loop module does not load that dependency by itself.
"""

import json
import os
from pathlib import Path
import re
import subprocess


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def evaluate() -> dict:
    workspace = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace / "prism" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    results = {}
    for mode in ("native", "prism"):
        script = workspace / "other_hyperon" / "PeTTa-OpenPSI" / "main" / "feedback-loop" / f"full-cycle-{mode}.metta"
        proc = subprocess.run(
            ["sh", "run.sh", str(script)],
            cwd=workspace / "PeTTa",
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
        output = ANSI_RE.sub("", proc.stdout + proc.stderr)
        if proc.returncode != 0:
            raise RuntimeError(f"{mode} feedback loop failed: {output[-2000:]}")
        label = mode.upper()

        def value(marker: str) -> str:
            matches = re.findall(rf"^\(FULL_CYCLE_{label}_{marker} (.*)\)$", output, re.M)
            if len(matches) != 1:
                raise RuntimeError(f"Expected one {mode}/{marker} result, got {matches}")
            return matches[0]

        results[mode] = {
            "plan": value("PLAN"),
            "plan_replays_to_goal": value("VALID") == "true",
            "demand_after": value("DEMAND"),
            "loop_reported_goal_met": "(goalMet true)" in output.splitlines(),
        }
        emotion = re.findall(rf"^\(FULL_CYCLE_{label} \((happinessValue .*)\)\)$", output, re.M)
        if len(emotion) != 1:
            raise RuntimeError(f"Missing {mode} emotion output")
        results[mode]["emotion_output"] = emotion[0]
    return {
        "backend": "iCog PeTTa-OpenPSI port through trueagi PeTTa",
        "fixture": "constructed three-rule graph, same initial state and demand; fresh process per mode",
        "native": results["native"],
        "prism": results["prism"],
        "interpretation": "Plan replay distinguishes modes; full-loop emotion/demand do not. The loop checks only the final action and the demand update does not occur in this fixture.",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
