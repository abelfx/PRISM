"""
End-to-End Benchmark Runner for PRISM.
Executes parameter sweeps over synthetic transitive chains, parses metrics,
and records structured JSON benchmarks.
"""

import argparse
import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional
from prism.benchmarks.utils.metrics import parse_selected_log
from prism.benchmarks.domains.transitive_chain import (
    generate_with_distractors,
    write_metta_file,
)

DEFAULT_PETTA_DIR = "/home/abel/Desktop/icog_labs/pln/PeTTa"
DEFAULT_TEMP_DIR = "/home/abel/Desktop/icog_labs/pln/prism/benchmarks/scratch"
DEFAULT_RESULTS_DIR = "/home/abel/Desktop/icog_labs/pln/prism/benchmarks/results"


def run_single(
    depth: int,
    n_distractors: int,
    guided: bool,
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    seed: int = 42,
    petta_dir: str = DEFAULT_PETTA_DIR,
    temp_dir: str = DEFAULT_TEMP_DIR,
) -> Dict[str, Any]:
    """Execute a single benchmark run on a synthetic transitive chain."""
    os.makedirs(temp_dir, exist_ok=True)
    mode_str = "guided" if guided else "unguided"
    temp_metta_path = os.path.join(
        temp_dir, f"chain_d{depth}_dist{n_distractors}_{mode_str}_s{seed}.metta"
    )

    spec = generate_with_distractors(
        depth=depth, n_distractors=n_distractors, seed=seed
    )
    write_metta_file(
        spec,
        temp_metta_path,
        max_steps=max_steps,
        task_queue_size=task_queue_size,
        belief_queue_size=belief_queue_size,
        guided=guided,
    )

    t0 = time.perf_counter()
    proc = subprocess.run(
        ["sh", "run.sh", temp_metta_path],
        cwd=petta_dir,
        capture_output=True,
        text=True,
    )
    wall_clock = time.perf_counter() - t0

    collector = parse_selected_log(
        proc.stdout, spec, guided=guided, wall_clock_s=wall_clock
    )
    res = collector.summary()
    res["seed"] = seed
    res["exit_code"] = proc.returncode

    # Clean up temp file
    try:
        if os.path.exists(temp_metta_path):
            os.remove(temp_metta_path)
    except Exception:
        pass

    return res


def run_sweep(
    depths: List[int],
    distractor_counts: List[int],
    guided: bool,
    repeats: int = 3,
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    output_json: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a parameter sweep across depths and distractor counts."""
    results: Dict[str, Any] = {
        "guided": guided,
        "depths": depths,
        "distractor_counts": distractor_counts,
        "repeats": repeats,
        "max_steps": max_steps,
        "runs": [],
        "aggregated": {},
    }

    print(
        f"\nStarting benchmark sweep: guided={guided} | depths={depths} | distractors={distractor_counts} | repeats={repeats}"
    )
    print("=" * 80)

    for depth in depths:
        for n_dist in distractor_counts:
            config_key = f"D{depth}_dist{n_dist}"
            config_runs = []

            for rep in range(repeats):
                seed = 100 + rep * 37
                print(
                    f"Running {config_key} (rep {rep+1}/{repeats}, seed={seed}, guided={guided})...",
                    end=" ",
                    flush=True,
                )
                run_res = run_single(
                    depth=depth,
                    n_distractors=n_dist,
                    guided=guided,
                    max_steps=max_steps,
                    task_queue_size=task_queue_size,
                    belief_queue_size=belief_queue_size,
                    seed=seed,
                )
                config_runs.append(run_res)
                results["runs"].append(run_res)
                status = "GOAL_REACHED" if run_res["goal_reached"] else "MISSED"
                print(
                    f"[{status}] waste={run_res['waste_ratio_pct']} time={run_res['wall_clock_seconds']}s"
                )

            # Aggregate statistics
            success_count = sum(1 for r in config_runs if r["goal_reached"])
            avg_waste = sum(r["waste_ratio"] for r in config_runs) / len(
                config_runs
            )
            avg_time = sum(r["wall_clock_seconds"] for r in config_runs) / len(
                config_runs
            )
            avg_steps = sum(r["steps_taken"] for r in config_runs) / len(
                config_runs
            )
            avg_distractor_picks = sum(
                r["distractor_selections"] for r in config_runs
            ) / len(config_runs)

            results["aggregated"][config_key] = {
                "depth": depth,
                "n_distractors": n_dist,
                "success_rate": round(success_count / repeats, 2),
                "avg_waste_ratio": round(avg_waste, 4),
                "avg_waste_ratio_pct": f"{avg_waste:.2%}",
                "avg_wall_clock_seconds": round(avg_time, 4),
                "avg_steps": round(avg_steps, 1),
                "avg_distractor_selections": round(avg_distractor_picks, 1),
            }

    if output_json:
        os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
        with open(output_json, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved benchmark results to: {output_json}")

    return results


def format_markdown_table(results: Dict[str, Any]) -> str:
    """Format aggregated results as a GitHub markdown table."""
    mode = "PRISM-Guided (Tier 1 v1)" if results["guided"] else "Unguided PLN (Baseline)"
    lines = [
        f"### Benchmark Results: {mode}",
        "",
        "| Depth | Distractors | Success Rate | Avg Waste Ratio | Avg Steps | Avg Distractor Picks | Avg Wall Clock |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for key, agg in results["aggregated"].items():
        succ = f"{int(agg['success_rate']*100)}%"
        lines.append(
            f"| D={agg['depth']} | {agg['n_distractors']} | {succ} | {agg['avg_waste_ratio_pct']} | {agg['avg_steps']} | {agg['avg_distractor_selections']} | {agg['avg_wall_clock_seconds']}s |"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PRISM Benchmark Runner")
    parser.add_argument(
        "--guided",
        action="store_true",
        default=False,
        help="Run in PRISM-guided mode (default: unguided)",
    )
    parser.add_argument(
        "--depths",
        type=int,
        nargs="+",
        default=[5, 8, 10],
        help="List of chain depths to evaluate",
    )
    parser.add_argument(
        "--distractors",
        type=int,
        nargs="+",
        default=[0, 10, 25, 50],
        help="List of distractor counts to evaluate",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Repetitions per configuration",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=100,
        help="Step budget for PLN",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path",
    )

    args = parser.parse_args()

    default_out = (
        os.path.join(DEFAULT_RESULTS_DIR, "baseline_guided_v1.json")
        if args.guided
        else os.path.join(DEFAULT_RESULTS_DIR, "baseline_unguided.json")
    )
    out_path = args.output or default_out

    res = run_sweep(
        depths=args.depths,
        distractor_counts=args.distractors,
        guided=args.guided,
        repeats=args.repeats,
        max_steps=args.max_steps,
        output_json=out_path,
    )
    print("\n" + format_markdown_table(res))
