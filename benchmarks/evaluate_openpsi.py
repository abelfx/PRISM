"""Run matched selector comparisons against live PeTTa-OpenPSI functions.

This evaluates one-step selection within an identical bounded traversal. It
does not evaluate real-world action execution or the full OpenPsi agent loop.
"""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import statistics
import subprocess


GOALS = (
    "Send-Greeting", "Receive-User-Response", "Understand-Initial-Mood",
    "Understand-Initial-Context", "Explore-Mood-Details", "Ask-Daily-Activities",
    "Learn-Activity-Details", "Understand-Hobby-Preferences", "Understand-Future-Goals",
    "Summarize-User-Preferences", "Understand-User-Interests", "Ask-Recent-Events",
    "Learn-Recent-Event-Details", "Understand-Event-Impact", "Explore-Event-Emotions",
    "Understand-Event-Significance", "Propose-Related-Topics", "Receive-Topic-Choice",
    "Discuss-Chosen-Topic", "Off-Topic-Discussion", "Irrelevant-Topic",
)

RESULT_RE = re.compile(
    r"^\(OPENPSI_EVAL ([\w-]+) (Native|PRISM) "
    r"\(Result (\w+) (\d+)\) ([\d.eE+-]+)\)$"
)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def evaluate() -> dict:
    workspace = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace / "prism" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        ["sh", "run.sh", str(workspace / "prism" / "benchmarks" / "evaluate_openpsi.metta")],
        cwd=workspace / "PeTTa",
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    output = ANSI_RE.sub("", proc.stdout + proc.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"PeTTa exited {proc.returncode}: {output[-3000:]}")

    runs: list[dict] = []
    conversation_plan: list[str] | None = None
    for line in output.splitlines():
        plan_match = re.fullmatch(r"\(OPENPSI_CONVERSATION_PLAN \((.*)\)\)", line)
        if plan_match:
            conversation_plan = plan_match.group(1).split()
        match = RESULT_RE.fullmatch(line)
        if match is None:
            continue
        case, mode, outcome, steps, seconds = match.groups()
        runs.append({
            "case": case,
            "mode": mode,
            "outcome": outcome,
            "steps": int(steps),
            "elapsed_ms": float(seconds) * 1000,
        })

    by_case: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        by_case[run["case"]][run["mode"]].append(run)

    expected = {"direct", "missing", "noisy5", "noisy20", "noisy50", "conversation2", "conversationDeep", "reverseDeep", "reverseOffTopic", *GOALS}
    if set(by_case) != expected | {"warmup"}:
        raise RuntimeError(f"Unexpected cases: {set(by_case) ^ (expected | {'warmup'})}")
    for case in expected:
        if set(by_case[case]) != {"Native", "PRISM"}:
            raise RuntimeError(f"Missing mode in {case}")
        for mode, observations in by_case[case].items():
            expected_count = 20 if case in {"direct", "missing", "noisy5", "noisy20", "noisy50"} else 5 if case in {"conversation2", "conversationDeep", "reverseDeep", "reverseOffTopic"} else 3
            if len(observations) != expected_count:
                raise RuntimeError(f"Missing observations in {case}/{mode}")
            if len({(o["outcome"], o["steps"]) for o in observations}) != 1:
                raise RuntimeError(f"Non-deterministic outcome in {case}/{mode}")
    if conversation_plan is None or len(conversation_plan) != 8:
        raise RuntimeError("Missing or malformed eight-action OpenPsi conversation plan")

    v1_proc = subprocess.run(
        ["sh", "run.sh", str(workspace / "prism" / "benchmarks" / "evaluate_openpsi_v1.metta")],
        cwd=workspace / "PeTTa",
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    v1_output = ANSI_RE.sub("", v1_proc.stdout + v1_proc.stderr)
    if v1_proc.returncode != 0:
        raise RuntimeError(f"OpenPsi v1 diagnostic exited {v1_proc.returncode}: {v1_output[-3000:]}")
    v1_lines = set(v1_output.splitlines())
    v1_expected = {
        "(OPENPSI_V1_SHORT_VALID true)",
        "(OPENPSI_V1_DEEP_VALID false)",
        "(OPENPSI_PRISM_DEEP_VALID true)",
    }
    if not v1_expected.issubset(v1_lines):
        raise RuntimeError(f"OpenPsi v1 diagnostic missing markers: {v1_expected - v1_lines}")

    v1_plans = {}
    for label in ("OPENPSI_V1_SHORT_PLAN", "OPENPSI_V1_DEEP_PLAN", "OPENPSI_PRISM_DEEP_PLAN"):
        matching = [line for line in v1_lines if re.fullmatch(rf"\({label} \((.*)\)\)", line)]
        if len(matching) != 1:
            raise RuntimeError(f"Missing or duplicate {label} plan")
        v1_plans[label] = re.fullmatch(rf"\({label} \((.*)\)\)", matching[0]).group(1).split()

    cases = {}
    for case in sorted(expected):
        cases[case] = {}
        for mode in ("Native", "PRISM"):
            observations = by_case[case][mode]
            cases[case][mode] = {
                "repeats": len(observations),
                "successes": sum(o["outcome"] == "Success" for o in observations),
                "outcome": observations[0]["outcome"],
                "steps": observations[0]["steps"],
                "median_ms": statistics.median(o["elapsed_ms"] for o in observations),
            }

    return {
        "protocol": {
            "backend": "PeTTa-OpenPSI action-planner-v2",
            "native_selector": "findMinDistance",
            "prism_selector": "PRISM.OpenPsi.Select",
            "matched_loop": "OpenPsiEval.Plan",
            "goal_budget": 15,
            "note": "Repeated timings on fixed cases; repetitions are not independent queries. Python cold-load excluded from warm medians.",
        },
        "goal_sweep": {
            "distinct_goals": len(GOALS),
            "native_solved": sum(cases[g]["Native"]["outcome"] == "Success" for g in GOALS),
            "prism_solved": sum(cases[g]["PRISM"]["outcome"] == "Success" for g in GOALS),
        },
        "cold_python_load_ms": by_case["warmup"]["PRISM"][0]["elapsed_ms"],
        "conversation_deep_actions": conversation_plan,
        "native_v1_diagnostic": {
            "short_plan_replays_to_goal": True,
            "deep_plan_replays_to_goal": False,
            "prism_deep_plan_replays_to_goal": True,
            "plans": v1_plans,
            "note": "Separate unbounded native v1 planner diagnostic; not part of the matched-selector timing comparison.",
        },
        "cases": cases,
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Optional machine-readable result path")
    args = parser.parse_args()
    result = evaluate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "goal_sweep": result["goal_sweep"],
        "cold_python_load_ms": result["cold_python_load_ms"],
        "native_v1_diagnostic": result["native_v1_diagnostic"],
        "cases": result["cases"],
    }, indent=2))


if __name__ == "__main__":
    main()
