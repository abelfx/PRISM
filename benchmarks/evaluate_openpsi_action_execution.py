"""Run a real, effectful PeTTa-OpenPSI ping-pong action under two planners.

The repository's executePlan/ping functions mutate its goal space. This is
one turn in one environment, not a cross-agent or stochastic win-rate study.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


RESULT_RE = re.compile(
    r"^\(EXECUTION_RESULT (Native|Prism) (healthy|tired) "
    r"(\([^\n]*?\)) (true|false) ([\d.]+) ([\d.]+) ([\d.]+)\)$",
    re.M,
)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def evaluate() -> dict:
    workspace = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace / "prism" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    rows = {}
    for mode in ("native", "prism"):
        script = (
            workspace / "other_hyperon" / "PeTTa-OpenPSI" / "use-cases" /
            "ping-pong" / "test" / f"prism-execution-{mode}.metta"
        )
        proc = subprocess.run(
            ["sh", "run.sh", str(script)],
            cwd=workspace / "PeTTa",
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        output = ANSI_RE.sub("", proc.stdout + proc.stderr)
        if proc.returncode != 0 or "ERROR:" in output:
            raise RuntimeError(f"{mode} action execution failed: {output[-1500:]}")
        matches = RESULT_RE.findall(output)
        if len(matches) != 2:
            raise RuntimeError(f"Expected two {mode} execution results: {output[-1500:]}")
        for selector, condition, plan, applied, opponent, lost, energy in matches:
            if selector.lower() != mode or condition in rows.get(mode, {}):
                raise RuntimeError(f"Unexpected duplicate or selector: {matches}")
            rows.setdefault(mode, {})[condition] = {
                "plan": plan,
                "executor_completed": applied == "true",
                "ball_at_opponent": float(opponent),
                "ball_lost": float(lost),
                "motivation_after": float(energy),
                "task_completed": applied == "true" and float(opponent) == 1.0 and float(lost) == 0.0,
            }
    if rows["native"] != rows["prism"]:
        raise RuntimeError(f"One-turn outcomes differ unexpectedly: {rows}")
    return {
        "environment": "repository PeTTa-OpenPSI ping-pong-v3 executePlan/ping, fresh process per selector",
        "conditions": {"healthy": "initial motivation 1.0", "tired": "initial motivation 0.1"},
        "native_v2": rows["native"],
        "prism": rows["prism"],
        "interpretation": "Real one-turn action effects are equal; no demonstrated PRISM outcome gain in this use case.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
