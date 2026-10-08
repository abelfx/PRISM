"""Compare OpenPsi v1, v2 selection, and PRISM per goal in fresh PeTTa runs.

The returned-plan action budget is shared (15), but v1's *planning search*
is unbounded, unlike the bounded v2/PRISM traversal. A per-process timeout
contains that asymmetry rather than pretending it is a fair search-budget gate.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from benchmarks.evaluate_openpsi import ANSI_RE, GOALS


RESULT_RE = re.compile(
    r"^\(FRESH_EVAL (V1|V2|PRISM) ([\w-]+) (cold|warm) "
    r"\(RunResult (\w+) (\d+) \((.*?)\)\) ([\d.eE+-]+)\)$"
)


def evaluate(goals: tuple[str, ...] = GOALS) -> dict:
    workspace = Path(__file__).resolve().parents[2]
    template = (workspace / "prism" / "benchmarks" / "openpsi_fresh_goal_template.metta").read_text()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace / "prism" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    observations = []
    for goal in goals:
        for mode in ("V1", "V2", "PRISM"):
            source = template.replace("__MODE__", mode).replace("__GOAL__", goal)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".metta", prefix="openpsi-fresh-",
                dir=workspace / "prism" / "benchmarks", delete=False,
            ) as script:
                script.write(source)
                script_path = Path(script.name)
            try:
                start = time.perf_counter()
                try:
                    proc = subprocess.run(
                        ["sh", "run.sh", str(script_path)],
                        cwd=workspace / "PeTTa", env=env,
                        capture_output=True, text=True, timeout=5, check=False,
                    )
                except subprocess.TimeoutExpired:
                    observations.append({"goal": goal, "mode": mode, "outcome": "Timeout"})
                    continue
                process_ms = (time.perf_counter() - start) * 1000
                output = ANSI_RE.sub("", proc.stdout + proc.stderr)
                if proc.returncode != 0:
                    observations.append({
                        "goal": goal, "mode": mode, "outcome": "RuntimeError",
                        "diagnostic": output[-400:],
                    })
                    continue
                matches = [RESULT_RE.fullmatch(line) for line in output.splitlines()]
                found = [m for m in matches if m]
                if len(found) != 2 or {m.group(3) for m in found} != {"cold", "warm"}:
                    observations.append({
                        "goal": goal, "mode": mode, "outcome": "ProtocolError",
                        "diagnostic": output[-400:],
                    })
                    continue
                observation = {"goal": goal, "mode": mode, "process_ms": process_ms}
                for match in found:
                    _, parsed_goal, round_name, outcome, steps, plan, seconds = match.groups()
                    if parsed_goal != goal:
                        raise RuntimeError(f"Wrong goal in {mode} response: {parsed_goal}")
                    observation[round_name] = {
                        "outcome": outcome,
                        "steps": int(steps),
                        "actions": plan.split() if plan else [],
                        "elapsed_ms": float(seconds) * 1000,
                    }
                observations.append(observation)
            finally:
                script_path.unlink(missing_ok=True)

    totals = {}
    for mode in ("V1", "V2", "PRISM"):
        subset = [r for r in observations if r["mode"] == mode]
        totals[mode] = {
            "goals": len(subset),
            "solved": sum(r.get("cold", {}).get("outcome") == "Success" for r in subset),
            "invalid": sum(r.get("cold", {}).get("outcome") == "Invalid" for r in subset),
            "timeouts_or_errors": sum("cold" not in r for r in subset),
        }
    return {
        "protocol": {
            "backend": "iCog PeTTa-OpenPSI",
            "same_goals": list(goals),
            "max_returned_actions": 15,
            "fresh_process_per_goal_and_mode": True,
            "costs": "cold/warm planner call in ms, and fresh total process ms",
            "caveat": "v1 planner has no internal search budget; only returned plan length and a five-second process timeout are bounded",
        },
        "totals": totals,
        "observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goals", nargs="*", choices=GOALS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(tuple(args.goals) if args.goals else GOALS)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"totals": result["totals"], "observations": result["observations"]}, indent=2))


if __name__ == "__main__":
    main()
