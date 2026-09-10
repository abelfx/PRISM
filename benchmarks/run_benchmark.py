"""
End-to-End Benchmark Runner for PRISM.
Executes parameter sweeps over synthetic reasoning domains (transitive chains,
diamond DAGs, tree conjunctions), parses metrics, tracks proof path optimality,
and records structured JSON benchmarks and proof trace datasets.
"""

import argparse
import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from prism.benchmarks.domains.multipath_dag import (
    classify_diamond_solution,
    generate_diamond_with_distractors,
    write_diamond_metta_file,
)
from prism.benchmarks.domains.transitive_chain import (
    generate_with_distractors,
    write_metta_file,
)
from prism.benchmarks.domains.tree_dag import (
    generate_tree_with_distractors,
    verify_tree_conjunction_solution,
    write_tree_metta_file,
)
from prism.benchmarks.utils.metrics import parse_selected_log
from prism.benchmarks.utils.trace_logger import ProofTraceSession

DEFAULT_PETTA_DIR = "/home/abel/Desktop/icog_labs/pln/PeTTa"
DEFAULT_TEMP_DIR = "/home/abel/Desktop/icog_labs/pln/prism/benchmarks/scratch"
DEFAULT_RESULTS_DIR = "/home/abel/Desktop/icog_labs/pln/prism/benchmarks/results"


def run_single(
    domain: str,
    depth_param: Any,
    n_distractors: int,
    guided: bool,
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    seed: int = 42,
    petta_dir: str = DEFAULT_PETTA_DIR,
    temp_dir: str = DEFAULT_TEMP_DIR,
    export_traces_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a single benchmark run on a chosen synthetic domain."""
    os.makedirs(temp_dir, exist_ok=True)
    mode_str = "guided" if guided else "unguided"

    if domain == "diamond":
        d_short, d_long = depth_param
        temp_metta_path = os.path.join(
            temp_dir, f"diamond_s{d_short}_l{d_long}_dist{n_distractors}_{mode_str}_s{seed}.metta"
        )
        spec = generate_diamond_with_distractors(
            depth_short=d_short,
            depth_long=d_long,
            n_distractors=n_distractors,
            seed=seed,
        )
        write_diamond_metta_file(
            spec,
            temp_metta_path,
            max_steps=max_steps,
            task_queue_size=task_queue_size,
            belief_queue_size=belief_queue_size,
            guided=guided,
        )
    elif domain == "tree":
        d_left, d_right = depth_param
        temp_metta_path = os.path.join(
            temp_dir, f"tree_l{d_left}_r{d_right}_dist{n_distractors}_{mode_str}_s{seed}.metta"
        )
        spec = generate_tree_with_distractors(
            depth_left=d_left,
            depth_right=d_right,
            n_distractors=n_distractors,
            seed=seed,
        )
        write_tree_metta_file(
            spec,
            temp_metta_path,
            max_steps=max_steps,
            task_queue_size=task_queue_size,
            belief_queue_size=belief_queue_size,
            guided=guided,
        )
    else:  # default transitive chain
        depth = int(depth_param)
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

    # Optional trace export
    if export_traces_path:
        session = ProofTraceSession(
            domain_name=f"{domain}_{depth_param}_dist{n_distractors}_s{seed}",
            goal_expr=spec["goal"],
        )
        for item in collector.selected_history:
            stmt = item["statement"]
            stv = item["stv"]
            ev = " ".join(item["evidence"])
            sent_str = f"(Sentence ({stmt} (stv {stv[0]} {stv[1]})) ({ev}))"
            session.record_step(step=item["step"], sentence_expr=sent_str)
        session.finalize(collector.evidence_stamp)
        session.export_jsonl(export_traces_path)

    # Clean up temp file
    try:
        if os.path.exists(temp_metta_path):
            os.remove(temp_metta_path)
    except Exception:
        pass

    return res


def run_sweep(
    domain: str,
    depths: List[Any],
    distractor_counts: List[int],
    guided: bool,
    repeats: int = 3,
    max_steps: int = 100,
    task_queue_size: int = 30,
    belief_queue_size: int = 100,
    output_json: Optional[str] = None,
    export_traces: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a parameter sweep across depths and distractor counts."""
    results: Dict[str, Any] = {
        "domain": domain,
        "guided": guided,
        "depths": depths,
        "distractor_counts": distractor_counts,
        "repeats": repeats,
        "max_steps": max_steps,
        "runs": [],
        "aggregated": {},
    }

    print(
        f"\nStarting {domain} benchmark sweep: guided={guided} | depths={depths} | distractors={distractor_counts} | repeats={repeats}"
    )
    print("=" * 80)

    for depth_param in depths:
        for n_dist in distractor_counts:
            if domain == "diamond":
                config_key = f"D{depth_param[0]}_{depth_param[1]}_dist{n_dist}"
            elif domain == "tree":
                config_key = f"Tree_L{depth_param[0]}_R{depth_param[1]}_dist{n_dist}"
            else:
                config_key = f"D{depth_param}_dist{n_dist}"

            config_runs = []

            for rep in range(repeats):
                seed = 100 + rep * 37
                print(
                    f"Running {config_key} (rep {rep+1}/{repeats}, seed={seed}, guided={guided})...",
                    end=" ",
                    flush=True,
                )
                run_res = run_single(
                    domain=domain,
                    depth_param=depth_param,
                    n_distractors=n_dist,
                    guided=guided,
                    max_steps=max_steps,
                    task_queue_size=task_queue_size,
                    belief_queue_size=belief_queue_size,
                    seed=seed,
                    export_traces_path=export_traces,
                )
                config_runs.append(run_res)
                results["runs"].append(run_res)
                status = "GOAL_REACHED" if run_res["goal_reached"] else "MISSED"
                extra = ""
                if "solution_path" in run_res:
                    extra = f" path={run_res['solution_path']}"
                elif "conjunction_verified" in run_res:
                    extra = f" conj={run_res['conjunction_verified']}"
                print(
                    f"[{status}{extra}] waste={run_res['waste_ratio_pct']} time={run_res['wall_clock_seconds']}s"
                )

            # Aggregate statistics
            success_count = sum(1 for r in config_runs if r["goal_reached"])
            avg_waste = sum(r["waste_ratio"] for r in config_runs) / len(config_runs)
            avg_time = sum(r["wall_clock_seconds"] for r in config_runs) / len(config_runs)
            avg_steps = sum(r["steps_taken"] for r in config_runs) / len(config_runs)
            avg_distractor_picks = sum(
                r["distractor_selections"] for r in config_runs
            ) / len(config_runs)

            agg_entry: Dict[str, Any] = {
                "depth_param": depth_param,
                "n_distractors": n_dist,
                "success_rate": round(success_count / repeats, 2),
                "avg_waste_ratio": round(avg_waste, 4),
                "avg_waste_ratio_pct": f"{avg_waste:.2%}",
                "avg_wall_clock_seconds": round(avg_time, 4),
                "avg_steps": round(avg_steps, 1),
                "avg_distractor_selections": round(avg_distractor_picks, 1),
            }

            if domain == "diamond":
                shortcut_count = sum(
                    1 for r in config_runs if r.get("solution_path") == "SHORTCUT"
                )
                agg_entry["shortcut_rate"] = round(shortcut_count / repeats, 2)
            elif domain == "tree":
                conj_count = sum(
                    1 for r in config_runs if r.get("conjunction_verified") is True
                )
                agg_entry["conjunction_rate"] = round(conj_count / repeats, 2)

            results["aggregated"][config_key] = agg_entry

    if output_json:
        os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved benchmark results to: {output_json}")

    return results


def format_markdown_table(results: Dict[str, Any]) -> str:
    """Format aggregated results as a GitHub markdown table."""
    mode = "PRISM-Guided (Tier 1 v1)" if results["guided"] else "Unguided PLN (Baseline)"
    domain = results.get("domain", "chain").upper()
    lines = [
        f"### Benchmark Results: {domain} — {mode}",
        "",
        "| Configuration | Distractors | Success Rate | Avg Waste Ratio | Avg Steps | Avg Distractor Picks | Avg Wall Clock |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for key, agg in results["aggregated"].items():
        succ = f"{int(agg['success_rate']*100)}%"
        lines.append(
            f"| {key} | {agg['n_distractors']} | {succ} | {agg['avg_waste_ratio_pct']} | {agg['avg_steps']} | {agg['avg_distractor_selections']} | {agg['avg_wall_clock_seconds']}s |"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PRISM Benchmark Runner")
    parser.add_argument(
        "--domain",
        type=str,
        choices=["chain", "diamond", "tree"],
        default="chain",
        help="Benchmark domain type: chain, diamond, or tree (default: chain)",
    )
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
        help="List of chain depths to evaluate (for domain=chain)",
    )
    parser.add_argument(
        "--diamond-depths",
        type=str,
        nargs="+",
        default=["2:5", "3:6"],
        help="List of short:long depth pairs for diamond domain (e.g. 2:5 3:6)",
    )
    parser.add_argument(
        "--tree-depths",
        type=str,
        nargs="+",
        default=["2:2", "3:3"],
        help="List of left:right depth pairs for tree domain (e.g. 2:2 3:3)",
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
    parser.add_argument(
        "--export-traces",
        type=str,
        default=None,
        help="Path to export JSON Lines (.jsonl) step-by-step proof traces",
    )

    args = parser.parse_args()

    # Determine depth parameters based on domain
    if args.domain == "diamond":
        depth_params = []
        for pair in args.diamond_depths:
            parts = pair.split(":")
            depth_params.append((int(parts[0]), int(parts[1])))
    elif args.domain == "tree":
        depth_params = []
        for pair in args.tree_depths:
            parts = pair.split(":")
            depth_params.append((int(parts[0]), int(parts[1])))
    else:
        depth_params = args.depths

    default_out = (
        os.path.join(DEFAULT_RESULTS_DIR, f"baseline_{args.domain}_guided.json")
        if args.guided
        else os.path.join(DEFAULT_RESULTS_DIR, f"baseline_{args.domain}_unguided.json")
    )
    out_path = args.output or default_out

    res = run_sweep(
        domain=args.domain,
        depths=depth_params,
        distractor_counts=args.distractors,
        guided=args.guided,
        repeats=args.repeats,
        max_steps=args.max_steps,
        output_json=out_path,
        export_traces=args.export_traces,
    )
    print("\n" + format_markdown_table(res))
