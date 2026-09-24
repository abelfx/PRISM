"""Week 9 progressive tests over the provided external MeTTa KGs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess
import time
from typing import Any, Dict, List, Sequence

from benchmarks.domains.external_kg import (
    executable_edges,
    find_transitive_chain,
    load_relation,
    progressive_slice,
    to_inheritance_sentences,
)
from benchmarks.evaluate_scaling_generalization import (
    _search_metrics,
    stage0_pair_frontier,
)
from prism.core.config import SearchConfig
from prism.search.engine import AStarSearchEngine


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS = (
    ROOT / "wordnet_stv_clean.metta",
    ROOT / "output_prolog_ready.metta",
    ROOT / "kg.metta",
)


def _git_revision(path: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def evaluate_source(
    path: str | Path,
    sizes: Sequence[int],
    chain_depth: int,
    max_steps: int,
) -> Dict[str, Any]:
    load_started = time.perf_counter()
    kg = load_relation(path, "isa")
    load_seconds = time.perf_counter() - load_started
    proof_edges = find_transitive_chain(kg.edges, chain_depth)
    goal = ["Inheritance", proof_edges[0][0], proof_edges[-1][1]]
    executable_count = len(executable_edges(kg.edges))
    if len(kg.source_tv_counts) == 1 and kg.missing_tv_count == 0:
        applied_tv = kg.source_tv_counts[0][0]
    else:
        applied_tv = (0.8, 0.9)
    rows: List[Dict[str, Any]] = []
    boundary = 0

    for requested_size in sizes:
        if requested_size > kg.unique_edges:
            rows.append(
                {"requested_edges": requested_size, "status": "source_too_small"}
            )
            continue
        edges = progressive_slice(kg, requested_size, proof_edges)
        facts = to_inheritance_sentences(edges, *applied_tv)
        frontier_started = time.perf_counter()
        frontier = stage0_pair_frontier(facts, facts, goal)
        frontier_seconds = time.perf_counter() - frontier_started
        engine = AStarSearchEngine(
            SearchConfig(
                max_steps=max_steps,
                beam_width=1,
                guided=True,
                use_stage0_filter=True,
            )
        )
        result = engine.search(facts, facts, goal)
        metrics = _search_metrics(result)
        rows.append(
            {
                "requested_edges": requested_size,
                "status": "completed",
                "stage0_frontier": frontier,
                "frontier_seconds": frontier_seconds,
                "prism": metrics,
            }
        )
        if metrics["success"]:
            boundary = requested_size

    source_tv_policy = (
        "preserved uniform source TV"
        if len(kg.source_tv_counts) == 1 and kg.missing_tv_count == 0
        else "explicit benchmark default 0.8/0.9 for missing or mixed source TVs"
    )
    return {
        "source": kg.source_path,
        "source_sha256": kg.source_sha256,
        "load_seconds": load_seconds,
        "normalization": {
            "source_relation": kg.relation,
            "pln_relation": "Inheritance",
            "raw_relation_edges": kg.raw_relation_edges,
            "unique_nonself_edges": kg.unique_edges,
            "pln_executable_edges": executable_count,
            "duplicates_removed": kg.duplicate_edges,
            "self_loops_rejected": kg.self_loops,
            "unsupported_compound_lines": kg.unsupported_compound_lines,
            "source_tv_counts": [
                {"tv": list(tv), "count": count}
                for tv, count in kg.source_tv_counts
            ],
            "missing_tv_count": kg.missing_tv_count,
            "applied_tv": list(applied_tv),
            "tv_policy": source_tv_policy,
        },
        "proof": {
            "source_edges": [list(edge) for edge in proof_edges],
            "held_out_goal": goal,
            "goal_absent_from_source": (goal[1], goal[2]) not in set(kg.edges),
        },
        "sizes": rows,
        "largest_successful_tested_slice": boundary,
        "full_source_inference_claimed": False,
    }


def run_external_kg_suite(
    inputs: Sequence[str | Path] = DEFAULT_INPUTS,
    sizes: Sequence[int] = (100, 1000, 5000),
    chain_depth: int = 3,
    max_steps: int = 20,
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "reproducibility": {
            "python": platform.python_version(),
            "prism_revision": _git_revision(ROOT / "prism"),
            "petta_revision": _git_revision(ROOT / "PeTTa"),
            "pln_revision": _git_revision(ROOT / "PeTTa" / "repos" / "PLN"),
            "sizes": list(sizes),
            "chain_depth": chain_depth,
            "max_steps": max_steps,
        },
        "sources": [
            evaluate_source(path, sizes, chain_depth, max_steps) for path in inputs
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", default=[str(p) for p in DEFAULT_INPUTS])
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 1000, 5000])
    parser.add_argument("--chain-depth", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run_external_kg_suite(
        args.inputs, args.sizes, args.chain_depth, args.max_steps
    )
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
