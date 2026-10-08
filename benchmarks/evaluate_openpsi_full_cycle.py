"""Noninteractive evaluation of path-validated PeTTa-OpenPSI feedback loops.

Each selector runs in a fresh PeTTa process against the same selected
fixture: either a constructed three-rule graph or OpenPsi's conversation
rules. The local OpenPsi feedback loop now imports its normalization
dependency and validates the complete route before updating bounded demand.
"""

import json
import os
from pathlib import Path
import re
import subprocess


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def evaluate(scenario: str = "full") -> dict:
    if scenario not in {"full", "conversation"}:
        raise ValueError(f"Unknown OpenPsi fixture: {scenario}")
    workspace = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace / "prism" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    results = {}
    for mode in ("native", "prism"):
        script = workspace / "other_hyperon" / "PeTTa-OpenPSI" / "main" / "feedback-loop" / f"{scenario}-cycle-{mode}.metta"
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
        prefix = f"{scenario.upper()}_CYCLE_{label}"

        def value(marker: str) -> str:
            matches = re.findall(rf"^\({prefix}_{marker} (.*)\)$", output, re.M)
            if len(matches) != 1:
                raise RuntimeError(f"Expected one {mode}/{marker} result, got {matches}")
            return matches[0]

        results[mode] = {
            "plan": value("PLAN"),
            "plan_replays_to_goal": value("VALID") == "true",
            "demand_after": value("DEMAND"),
            "kb_demands_after": value("KB_DEMANDS"),
            "loop_reported_goal_met": "(goalMet true)" in output.splitlines(),
        }
        emotion = re.findall(rf"^\({prefix} \((happinessValue .*)\)\)$", output, re.M)
        if len(emotion) != 1:
            raise RuntimeError(f"Missing {mode} emotion output")
        results[mode]["emotion_output"] = emotion[0]
        if scenario == "full":
            results[mode]["second_demand_after"] = value("SECOND_DEMAND")
            results[mode]["second_kb_demands_after"] = value("SECOND_KB_DEMANDS")
            def demand_values(blob: str) -> dict[str, float]:
                found = re.findall(r"\(demand (\w+) 0\.3 0\.5 ([\d.]+)\)", blob)
                if len(found) != 3 or len({name for name, _ in found}) != 3:
                    raise RuntimeError(f"Duplicate or missing bounded demands: {blob}")
                return {name: float(number) for name, number in found}

            first = demand_values(results[mode]["kb_demands_after"])
            second = demand_values(results[mode]["second_kb_demands_after"])
            updated = [name for name in first if second[name] != first[name]]
            results[mode]["second_updated_demand"] = updated[0] if len(updated) == 1 else None
            if updated and (len(updated) != 1 or abs(second[updated[0]] -
                                                 (first[updated[0]] + 0.5 * (1 - first[updated[0]]))) > 1e-9):
                raise RuntimeError(f"Unexpected second-cycle demand update: {first} -> {second}")
    return {
        "backend": "iCog PeTTa-OpenPSI port through trueagi PeTTa",
        "fixture": (
            "repository conversation-rule graph with a fixed competence demand"
            if scenario == "conversation"
            else "constructed three-rule graph with a fixed competence demand"
        ) + "; fresh process per mode",
        "native": results["native"],
        "prism": results["prism"],
        "interpretation": (
            "After local path-validation and bounded-demand fixes, only PRISM's "
            "replay-valid plan updates demand and changes downstream emotion values. "
            "The action outcomes are still symbolic, not real-world execution."
        ),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("full", "conversation"), default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.scenario)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
