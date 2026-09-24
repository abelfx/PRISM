"""Week 9 scaling and cross-domain generalization benchmark.

The runner uses real ``PLN.Apply`` for every inference. It compares a frozen
Tier 1 + Stage 0 configuration with deterministic seeded-random candidate
ordering, reports Stage 0 pair-frontier reduction, and measures waste growth.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import subprocess
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

from prism.benchmarks.domains.multipath_dag import generate_diamond_with_distractors
from prism.benchmarks.domains.semantic_gap import generate_semantic_gap
from prism.benchmarks.domains.transitive_chain import generate_with_distractors
from prism.benchmarks.domains.tree_dag import generate_tree_with_distractors
from prism.benchmarks.evaluate_gap_rescue import format_facts as format_gap_facts
from prism.benchmarks.evaluate_search_comparison import format_spec_facts, format_spec_stvs
from prism.core.config import SearchConfig
from prism.search.engine import AStarSearchEngine, SearchResult
from prism.search.rules import parse_sentence
from prism.stage0 import extract_concepts, filter_beliefs


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RANDOM_SEEDS = (11, 23, 42, 67, 89)


def _git_revision(path: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _search_metrics(result: SearchResult) -> Dict[str, Any]:
    decisions = max(0, result.steps_expanded - 1)
    proof_actions = 0
    if result.goal_found and result.goal_sentence is not None:
        final_sentence = parse_sentence(result.goal_sentence)
        final_evidence = set(final_sentence.evidence_stamp) if final_sentence else set()
        for node in result.proof_path:
            action = parse_sentence(node.action)
            if not action or not action.evidence_stamp:
                continue
            action_evidence = set(action.evidence_stamp)
            if action_evidence.issubset(final_evidence):
                proof_actions += 1
    wasted = max(0, decisions - proof_actions) if result.goal_found else decisions
    return {
        "success": result.goal_found,
        "steps": result.steps_expanded,
        "nodes_generated": result.nodes_generated,
        "visited_states": result.visited_states_count,
        "proof_actions": proof_actions,
        "wasted_expansions": wasted,
        "waste_ratio": round(wasted / max(decisions, 1), 6),
        "wall_clock_seconds": result.wall_clock_seconds,
    }


def stage0_pair_frontier(
    tasks: Sequence[Any], beliefs: Sequence[Any], goal: Any
) -> Dict[str, int | float]:
    """Count premise pairs before and after the same Stage 0 policy as search."""
    parsed_tasks = [p for p in (parse_sentence(t) for t in tasks) if p]
    parsed_beliefs = [p for p in (parse_sentence(b) for b in beliefs) if p]
    raw_pairs = len(parsed_tasks) * len(parsed_beliefs)
    goal_concepts = extract_concepts(goal)
    connected = [
        task
        for task in parsed_tasks
        if len(task.evidence_stamp) >= 2
        or bool(extract_concepts(task.raw) & goal_concepts)
    ] or parsed_tasks
    filtered_pairs = sum(
        len(filter_beliefs(task.raw, goal, beliefs)) for task in connected
    )
    reduction = 1.0 - (filtered_pairs / max(raw_pairs, 1))
    return {
        "raw_pairs": raw_pairs,
        "filtered_pairs": filtered_pairs,
        "reduction": round(reduction, 6),
    }


def seeded_random_generator(
    seed: int,
    concept_stvs: Dict[str, Tuple[float, float]],
) -> Callable[[Sequence[Any], Sequence[Any]], List[Any]]:
    """Return a deterministic, goal-blind random candidate ordering baseline."""
    rng = random.Random(seed)

    def generate(tasks: Sequence[Any], beliefs: Sequence[Any]) -> List[Any]:
        from prism.search.pln_runtime import apply_pln_pair

        parsed_tasks = [p for p in (parse_sentence(item) for item in tasks) if p]
        parsed_beliefs = [p for p in (parse_sentence(item) for item in beliefs) if p]
        pairs = [
            (task, belief)
            for task in parsed_tasks
            for belief in parsed_beliefs
            if task.relation == belief.relation
            and (
                task.object_node == belief.subject
                or belief.object_node == task.subject
                or task.subject == belief.subject
                or task.object_node == belief.object_node
            )
        ]
        rng.shuffle(pairs)
        existing = {
            (
                belief.relation,
                belief.subject,
                belief.object_node,
                belief.evidence_stamp,
            )
            for belief in parsed_beliefs
        }
        for task, belief in pairs:
            result = apply_pln_pair(task, belief, concept_stvs)
            parsed = parse_sentence(result)
            if parsed is None:
                continue
            signature = (
                parsed.relation,
                parsed.subject,
                parsed.object_node,
                parsed.evidence_stamp,
            )
            if signature not in existing:
                # The random baseline always uses beam_width=1. Once the first
                # legal action in shuffled pair order is known, later PLN calls
                # cannot affect the state selected by the search engine.
                return [result]
        return []

    return generate


def _run_pair(
    facts: Sequence[Any],
    stvs: Dict[str, Tuple[float, float]],
    goal: Any,
    max_steps: int,
    seed: int,
) -> Dict[str, Any]:
    random_metrics = _run_random(facts, stvs, goal, max_steps, seed)
    prism_metrics = _run_prism(facts, stvs, goal, max_steps)
    return {"random": random_metrics, "prism": prism_metrics}


def _run_random(
    facts: Sequence[Any],
    stvs: Dict[str, Tuple[float, float]],
    goal: Any,
    max_steps: int,
    seed: int,
) -> Dict[str, Any]:
    result = AStarSearchEngine(
        SearchConfig(
            max_steps=max_steps,
            beam_width=1,
            guided=False,
            use_stage0_filter=False,
        )
    ).search(
        facts,
        facts,
        goal,
        candidate_generator=seeded_random_generator(seed, stvs),
        concept_stvs=stvs,
    )
    return _search_metrics(result)


def _run_prism(
    facts: Sequence[Any],
    stvs: Dict[str, Tuple[float, float]],
    goal: Any,
    max_steps: int,
) -> Dict[str, Any]:
    result = AStarSearchEngine(
        SearchConfig(
            max_steps=max_steps,
            beam_width=1,
            guided=True,
            use_stage0_filter=True,
        )
    ).search(facts, facts, goal, concept_stvs=stvs)
    return _search_metrics(result)


def aggregate_trials(trials: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize repeated search trials without hiding individual outcomes."""
    if not trials:
        raise ValueError("at least one trial is required")
    successes = sum(int(trial["success"]) for trial in trials)
    return {
        "trials": len(trials),
        "successes": successes,
        "success_rate": round(successes / len(trials), 6),
        "mean_steps": round(sum(trial["steps"] for trial in trials) / len(trials), 6),
        "mean_wasted_expansions": round(
            sum(trial["wasted_expansions"] for trial in trials) / len(trials), 6
        ),
        "min_wasted_expansions": min(
            trial["wasted_expansions"] for trial in trials
        ),
        "max_wasted_expansions": max(
            trial["wasted_expansions"] for trial in trials
        ),
    }


def scaling_exponent(points: Iterable[Tuple[int, int]]) -> float:
    """Least-squares log-log exponent for waste+1 versus fact count."""
    values = [(math.log(max(x, 1)), math.log(max(y, 0) + 1)) for x, y in points]
    if len(values) < 2:
        return 0.0
    mean_x = sum(x for x, _ in values) / len(values)
    mean_y = sum(y for _, y in values) / len(values)
    denominator = sum((x - mean_x) ** 2 for x, _ in values)
    if denominator == 0.0:
        return 0.0
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in values)
    return round(numerator / denominator, 6)


def run_scaling(
    sizes: Sequence[int],
    depth: int,
    max_steps: int,
    seed: int,
    random_seeds: Sequence[int] = DEFAULT_RANDOM_SEEDS,
) -> Dict[str, Any]:
    if not random_seeds:
        raise ValueError("random_seeds must not be empty")
    rows: List[Dict[str, Any]] = []
    for distractors in sizes:
        spec = generate_with_distractors(depth, distractors, seed=seed)
        facts = format_spec_facts(spec)
        stvs = format_spec_stvs(spec)
        goal = spec["goal"]
        row = {
            "distractors": distractors,
            "facts": len(facts),
            "stage0_frontier": stage0_pair_frontier(facts, facts, goal),
        }
        random_trials = [
            {"seed": random_seed, **_run_random(facts, stvs, goal, max_steps, random_seed)}
            for random_seed in random_seeds
        ]
        primary = next(
            (trial for trial in random_trials if trial["seed"] == seed),
            random_trials[0],
        )
        row.update(
            {
                "random": {k: v for k, v in primary.items() if k != "seed"},
                "random_trials": random_trials,
                "random_aggregate": aggregate_trials(random_trials),
                "prism": _run_prism(facts, stvs, goal, max_steps),
            }
        )
        rows.append(row)

    exponents_by_seed = [
        {
            "seed": random_seed,
            "waste_exponent": scaling_exponent(
                (
                    row["facts"],
                    next(
                        trial["wasted_expansions"]
                        for trial in row["random_trials"]
                        if trial["seed"] == random_seed
                    ),
                )
                for row in rows
            ),
        }
        for random_seed in random_seeds
    ]

    return {
        "domain": "transitive_chain",
        "depth": depth,
        "max_steps": max_steps,
        "random_seeds": list(random_seeds),
        "sizes": rows,
        "random_waste_exponent": scaling_exponent(
            (row["facts"], row["random"]["wasted_expansions"]) for row in rows
        ),
        "prism_waste_exponent": scaling_exponent(
            (row["facts"], row["prism"]["wasted_expansions"]) for row in rows
        ),
        "random_waste_exponents_by_seed": exponents_by_seed,
        "mean_random_waste_exponent": round(
            sum(item["waste_exponent"] for item in exponents_by_seed)
            / len(exponents_by_seed),
            6,
        ),
    }


def _cross_domain_specs() -> List[Tuple[str, Dict[str, Any], bool]]:
    return [
        ("chain", generate_with_distractors(5, 20, seed=42), False),
        ("diamond", generate_diamond_with_distractors(3, 7, 20, seed=42), False),
        ("tree", generate_tree_with_distractors(3, 3, 20, seed=42), False),
        (
            "semantic_gap",
            generate_semantic_gap(
                depth_source=2,
                depth_target=2,
                n_distractors=0,
                n_goal_decoys=5,
                include_bridge_support=True,
                seed=42,
            ),
            True,
        ),
    ]


def run_cross_domain(
    max_steps: int,
    seed: int,
    random_seeds: Sequence[int] = DEFAULT_RANDOM_SEEDS,
) -> Dict[str, Any]:
    if not random_seeds:
        raise ValueError("random_seeds must not be empty")
    rows: List[Dict[str, Any]] = []
    for name, spec, is_gap in _cross_domain_specs():
        facts = format_gap_facts(spec) if is_gap else format_spec_facts(spec)
        stvs = format_spec_stvs(spec)
        trials = [
            {
                "seed": random_seed,
                **_run_random(facts, stvs, spec["goal"], max_steps, random_seed),
            }
            for random_seed in random_seeds
        ]
        primary = next(
            (trial for trial in trials if trial["seed"] == seed), trials[0]
        )
        row = {
            "domain": name,
            "facts": len(facts),
            "goal": spec["goal"],
            "random": {k: v for k, v in primary.items() if k != "seed"},
            "random_trials": trials,
            "random_aggregate": aggregate_trials(trials),
            "prism": _run_prism(facts, stvs, spec["goal"], max_steps),
        }
        rows.append(row)
    random_successes = sum(int(row["random"]["success"]) for row in rows)
    prism_successes = sum(int(row["prism"]["success"]) for row in rows)
    total_random_successes = sum(
        row["random_aggregate"]["successes"] for row in rows
    )
    total_random_trials = len(rows) * len(random_seeds)
    random_success_rate = total_random_successes / max(total_random_trials, 1)
    prism_success_rate = prism_successes / max(len(rows), 1)
    return {
        "max_steps": max_steps,
        "seed": seed,
        "random_seeds": list(random_seeds),
        "domains": rows,
        "random_successes": random_successes,
        "prism_successes": prism_successes,
        "aggregate_random_successes": total_random_successes,
        "aggregate_random_trials": total_random_trials,
        "aggregate_random_success_rate": round(random_success_rate, 6),
        "prism_success_rate": round(prism_success_rate, 6),
        "passes_random_baseline": prism_success_rate > random_success_rate,
    }


def run_week9(
    sizes: Sequence[int] = (0, 10, 25, 50),
    depth: int = 5,
    scaling_steps: int = 30,
    cross_domain_steps: int = 20,
    seed: int = 42,
    random_seeds: Sequence[int] = DEFAULT_RANDOM_SEEDS,
) -> Dict[str, Any]:
    scaling = run_scaling(sizes, depth, scaling_steps, seed, random_seeds)
    cross_domain = run_cross_domain(cross_domain_steps, seed, random_seeds)
    largest = scaling["sizes"][-1]
    return {
        "schema_version": 2,
        "seed": seed,
        "reproducibility": {
            "prism_revision": _git_revision(ROOT / "prism"),
            "petta_revision": _git_revision(ROOT / "PeTTa"),
            "pln_revision": _git_revision(ROOT / "PeTTa" / "repos" / "PLN"),
            "sizes": list(sizes),
            "depth": depth,
            "scaling_steps": scaling_steps,
            "cross_domain_steps": cross_domain_steps,
            "random_seeds": list(random_seeds),
        },
        "scaling": scaling,
        "cross_domain": cross_domain,
        "gates": {
            "stage0_reduction_at_least_40pct": (
                largest["stage0_frontier"]["reduction"] >= 0.40
            ),
            "prism_waste_growth_sublinear": scaling["prism_waste_exponent"] < 1.0,
            "prism_waste_growth_below_random": (
                scaling["prism_waste_exponent"]
                < scaling["mean_random_waste_exponent"]
            ),
            "cross_domain_beats_random": cross_domain["passes_random_baseline"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[0, 10, 25, 50])
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--scaling-steps", type=int, default=30)
    parser.add_argument("--cross-domain-steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--random-seeds",
        nargs="+",
        type=int,
        default=list(DEFAULT_RANDOM_SEEDS),
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run_week9(
        sizes=args.sizes,
        depth=args.depth,
        scaling_steps=args.scaling_steps,
        cross_domain_steps=args.cross_domain_steps,
        seed=args.seed,
        random_seeds=args.random_seeds,
    )
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
