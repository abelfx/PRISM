"""Collect, train, and evaluate the Week 11 Tier 1 v2 model."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import subprocess
import statistics
import time
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np

from benchmarks.domains.multipath_dag import generate_diamond_with_distractors
from benchmarks.domains.transitive_chain import generate_with_distractors
from benchmarks.domains.tree_dag import generate_tree_with_distractors
from benchmarks.evaluate_search_comparison import format_spec_facts, format_spec_stvs
from prism.core.config import SearchConfig
from prism.observability.tracing import ProofTraceSession
from prism.search.engine import AStarSearchEngine
from prism.training.dataset import TraceExample, load_trace_jsonl, split_by_run
from prism.training.model import TrainConfig, train_model

ROOT = Path(__file__).resolve().parents[1]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _revision() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _specs() -> Iterable[Tuple[str, Dict[str, Any]]]:
    for seed in (11, 23, 42, 67):
        for depth in (3, 4):
            yield f"chain-d{depth}-s{seed}", generate_with_distractors(depth, 5, seed=seed)
        yield f"diamond-s{seed}", generate_diamond_with_distractors(2, 5, 5, seed=seed)
        yield f"tree-s{seed}", generate_tree_with_distractors(2, 2, 5, seed=seed)


def collect_traces(path: Path) -> Dict[str, Any]:
    """Run real PLN-backed searches and export finalized candidate labels."""
    if path.exists():
        path.unlink()
    runs = []
    for run_id, spec in _specs():
        facts = format_spec_facts(spec)
        session = ProofTraceSession(run_id, spec["goal"])
        # Disable Stage 0 only for corpus collection. This exposes the broader
        # legal candidate frontier that Tier 1 must rank instead of handing the
        # trainer an already-solved one-candidate shortlist.
        result = AStarSearchEngine(SearchConfig(
            max_steps=80, beam_width=5, guided=True, use_stage0_filter=False,
        )).search(
            facts, facts, spec["goal"], trace_session=session,
            concept_stvs=format_spec_stvs(spec),
        )
        session.export_jsonl(str(path))
        runs.append({"run_id": run_id, "goal_found": result.goal_found, "examples": len(session.steps)})
    return {"runs": runs, "successful_runs": sum(int(x["goal_found"]) for x in runs)}


def _ranking_metrics(examples: Sequence[TraceExample], scores: Sequence[float]) -> Dict[str, float | int]:
    groups: Dict[Tuple[str, int], List[Tuple[TraceExample, float]]] = defaultdict(list)
    for item, score in zip(examples, scores):
        groups[(item.run_id, item.step)].append((item, float(score)))
    eligible = [values for values in groups.values() if any(item.outcome for item, _ in values)]
    def hit_rate(k: int) -> float:
        hits = 0
        for values in eligible:
            ranked = sorted(values, key=lambda pair: pair[1], reverse=True)[:k]
            hits += int(any(item.outcome for item, _ in ranked))
        return round(hits / max(1, len(eligible)), 6)
    reciprocal_ranks = []
    for values in eligible:
        ranked = sorted(values, key=lambda pair: pair[1], reverse=True)
        first_positive = next(index for index, (item, _) in enumerate(ranked, 1) if item.outcome)
        reciprocal_ranks.append(1.0 / first_positive)
    return {
        "eligible_decisions": len(eligible),
        "top1_hit_rate": hit_rate(1),
        "top3_hit_rate": hit_rate(3),
        "mean_reciprocal_rank": round(sum(reciprocal_ranks) / max(1, len(reciprocal_ranks)), 6),
    }


def _roc_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    order = np.argsort(scores, kind="stable")
    ranks = np.empty(len(scores), dtype=float)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and scores[order[end]] == scores[order[start]]:
            end += 1
        ranks[order[start:end]] = ((start + 1) + end) / 2.0
        start = end
    rank_sum = ranks[labels == 1].sum()
    return float((rank_sum - positives * (positives + 1) / 2) / (positives * negatives))


def _average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    positives = int(labels.sum())
    if positives == 0:
        return float("nan")
    order = np.argsort(-scores, kind="stable")
    ranked = labels[order]
    precision = np.cumsum(ranked) / np.arange(1, len(ranked) + 1)
    return float((precision * ranked).sum() / positives)


def _classification_metrics(examples: Sequence[TraceExample], scores: Sequence[float]) -> Dict[str, Any]:
    labels = np.asarray([item.outcome for item in examples], dtype=int)
    probabilities = np.clip(np.asarray(scores, dtype=float), 1e-7, 1.0 - 1e-7)
    predicted = probabilities >= 0.5
    tp = int(((predicted == 1) & (labels == 1)).sum())
    tn = int(((predicted == 0) & (labels == 0)).sum())
    fp = int(((predicted == 1) & (labels == 0)).sum())
    fn = int(((predicted == 0) & (labels == 1)).sum())
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    bins = np.linspace(0.0, 1.0, 11)
    ece = 0.0
    for lower, upper in zip(bins[:-1], bins[1:]):
        mask = (probabilities >= lower) & (probabilities < upper if upper < 1.0 else probabilities <= upper)
        if mask.any():
            ece += float(mask.mean()) * abs(float(labels[mask].mean()) - float(probabilities[mask].mean()))
    return {
        "examples": len(labels), "positives": int(labels.sum()), "negatives": int((labels == 0).sum()),
        "accuracy": round((tp + tn) / max(1, len(labels)), 6),
        "balanced_accuracy": round((recall + specificity) / 2.0, 6),
        "precision": round(precision, 6), "recall": round(recall, 6),
        "specificity": round(specificity, 6), "f1": round(f1, 6),
        "roc_auc": round(_roc_auc(labels, probabilities), 6),
        "average_precision": round(_average_precision(labels, probabilities), 6),
        "log_loss": round(float(-np.mean(labels * np.log(probabilities) + (1 - labels) * np.log(1 - probabilities))), 6),
        "brier_score": round(float(np.mean((probabilities - labels) ** 2)), 6),
        "expected_calibration_error_10_bin": round(ece, 6),
        "confusion_matrix": {"true_positive": tp, "true_negative": tn, "false_positive": fp, "false_negative": fn},
    }


def _group_folds(examples: Sequence[TraceExample], folds: int, seed: int) -> List[Tuple[List[TraceExample], List[TraceExample]]]:
    run_ids = sorted({item.run_id for item in examples})
    rng = np.random.default_rng(seed)
    rng.shuffle(run_ids)
    buckets = [set(run_ids[index::folds]) for index in range(folds)]
    return [
        ([item for item in examples if item.run_id not in held_out], [item for item in examples if item.run_id in held_out])
        for held_out in buckets
    ]


def evaluate(
    trace_path: Path,
    model_path: Path,
    output_path: Path,
    seed: int = 42,
    epochs: int = 120,
) -> Dict[str, Any]:
    examples = load_trace_jsonl([trace_path])
    train, validation = split_by_run(examples, validation_fraction=.25, seed=seed)
    config = TrainConfig(epochs=epochs, seed=seed)
    started = time.perf_counter()
    model, history = train_model(train, config, validation)
    training_seconds = time.perf_counter() - started
    model.save(model_path)
    v2_scores = model.predict_examples(validation)
    v1_scores = [item.heuristic_score for item in validation]
    train_scores = model.predict_examples(train)
    v1_metrics = _ranking_metrics(validation, v1_scores)
    v2_metrics = _ranking_metrics(validation, v2_scores)
    gate = bool(v2_metrics["top1_hit_rate"] >= v1_metrics["top1_hit_rate"])
    probe = validation[0]
    model.score(probe.candidate, probe.goal, probe.strength, probe.confidence, probe.depth)
    timings = []
    for _ in range(1000):
        tick = time.perf_counter_ns()
        model.score(probe.candidate, probe.goal, probe.strength, probe.confidence, probe.depth)
        timings.append((time.perf_counter_ns() - tick) / 1_000_000.0)
    latency = {
        "samples": len(timings),
        "median_ms": round(statistics.median(timings), 6),
        "p95_ms": round(sorted(timings)[int(.95 * len(timings)) - 1], 6),
        "target_ms": 0.5,
        "passed": statistics.median(timings) < 0.5,
    }

    without_queue_train = [replace(item, queue_position=0, candidate_pool_size=1) for item in train]
    without_queue_validation = [replace(item, queue_position=0, candidate_pool_size=1) for item in validation]
    ablation_model, ablation_history = train_model(
        without_queue_train,
        TrainConfig(epochs=epochs, seed=seed),
        without_queue_validation,
    )
    ablation_scores = ablation_model.predict_examples(without_queue_validation)

    cross_validation = []
    for fold_index, (fold_train, fold_validation) in enumerate(_group_folds(examples, 4, seed), 1):
        fold_model, fold_history = train_model(
            fold_train,
            TrainConfig(epochs=min(80, epochs), seed=seed + fold_index),
            fold_validation,
        )
        fold_scores = fold_model.predict_examples(fold_validation)
        cross_validation.append({
            "fold": fold_index,
            "train_runs": len({item.run_id for item in fold_train}),
            "validation_runs": len({item.run_id for item in fold_validation}),
            "best_epoch": fold_history.best_epoch,
            "classification": _classification_metrics(fold_validation, fold_scores),
            "ranking": _ranking_metrics(fold_validation, fold_scores),
        })

    curve = [
        {
            "epoch": index + 1,
            "objective_loss": round(history.objective_loss[index], 8),
            "train_loss": round(history.train_loss[index], 8),
            "validation_loss": round(history.validation_loss[index], 8),
            "train_accuracy": round(history.train_accuracy[index], 8),
            "validation_accuracy": round(history.validation_accuracy[index], 8),
        }
        for index in range(history.stopped_epoch)
    ]
    artifact = {
        "schema_version": 1,
        "milestone": 11,
        "reproducibility": {"prism_revision": _revision(), "seed": seed, "train_config": asdict(config)},
        "dataset": {
            "trace_path": _display_path(trace_path), "trace_sha256": _sha256(trace_path),
            "examples": len(examples),
            "train_examples": len(train), "validation_examples": len(validation),
            "train_runs": sorted({x.run_id for x in train}),
            "validation_runs": sorted({x.run_id for x in validation}),
            "positive_examples": sum(x.outcome for x in examples),
        },
        "training": {
            "algorithm": "learned token embeddings + 128/64 ReLU MLP; class-balanced binary cross-entropy; full-batch Adam; early stopping on validation log loss",
            "seconds": round(training_seconds, 6),
            "best_epoch": history.best_epoch, "stopped_epoch": history.stopped_epoch,
            "curve": curve,
        },
        "train_metrics": _classification_metrics(train, train_scores),
        "held_out": {
            "classification": _classification_metrics(validation, v2_scores),
            "v1_ranking": v1_metrics,
            "v2_ranking": v2_metrics,
        },
        "queue_position_ablation": {
            "purpose": "Detect whether v2 merely learns the v1-derived queue rank feature.",
            "best_epoch": ablation_history.best_epoch,
            "classification": _classification_metrics(without_queue_validation, ablation_scores),
            "ranking": _ranking_metrics(without_queue_validation, ablation_scores),
        },
        "grouped_4_fold_cross_validation": cross_validation,
        "inference_latency": latency,
        "gate_v2_shortlist_accuracy_gte_v1": gate,
        "model_path": _display_path(model_path),
        "model_sha256": _sha256(model_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=ROOT / "artifacts/training/week11_traces.jsonl")
    parser.add_argument("--model", type=Path, default=ROOT / "artifacts/models/tier1_v2.npz")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks/results/reference/week11_tier1_v2.json")
    parser.add_argument("--skip-collection", action="store_true")
    parser.add_argument("--epochs", type=int, default=120)
    args = parser.parse_args()
    args.traces.parent.mkdir(parents=True, exist_ok=True)
    collection = None if args.skip_collection else collect_traces(args.traces)
    result = evaluate(args.traces, args.model, args.output, epochs=args.epochs)
    if collection is not None:
        result["collection"] = collection
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if (
        result["gate_v2_shortlist_accuracy_gte_v1"]
        and result["inference_latency"]["passed"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
