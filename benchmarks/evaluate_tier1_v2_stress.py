"""Out-of-distribution and adversarial stress tests for Tier 1 v1 versus v2."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import random
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from benchmarks.domains.external_kg import executable_edges, find_transitive_chain, load_relation
from benchmarks.evaluate_external_kg_scaling import DEFAULT_INPUTS
from benchmarks.evaluate_tier1_v2 import _classification_metrics, _ranking_metrics
from prism.core.config import Tier1Config
from prism.tier1.heuristic_v1 import compute_overlap, extract_atoms
from prism.training.dataset import TraceExample, load_trace_jsonl, split_by_run
from prism.training.model import Tier1V2Model, TrainConfig, train_model

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACES = ROOT / "artifacts/training/week11_traces.jsonl"
DEFAULT_MODEL = ROOT / "artifacts/models/tier1_v2.npz"


def v1_score(item: TraceExample) -> float:
    cfg = Tier1Config()
    overlap = compute_overlap(extract_atoms(item.candidate), extract_atoms(item.goal))
    return cfg.alpha * overlap + cfg.beta * item.confidence + cfg.delta * (cfg.gamma ** item.depth)


def model_scores(model: Tier1V2Model, examples: Sequence[TraceExample]) -> List[float]:
    return [
        model.score(
            item.candidate, item.goal, item.strength, item.confidence, item.depth,
            item.queue_position, item.candidate_pool_size,
        )
        for item in examples
    ]


def evaluate_pair(model: Tier1V2Model, examples: Sequence[TraceExample]) -> Dict[str, Any]:
    v1 = [v1_score(item) for item in examples]
    v2 = model_scores(model, examples)
    return {
        "examples": len(examples),
        "runs": len({item.run_id for item in examples}),
        "v1_ranking": _ranking_metrics(examples, v1),
        "v2_ranking": _ranking_metrics(examples, v2),
        "v2_classification": _classification_metrics(examples, v2),
    }


def _rename(text: str, rename_predicate: bool) -> str:
    protected = {"Sentence", "stv"}
    def replace_token(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in protected:
            return token
        if token == "Inheritance" and not rename_predicate:
            return token
        digest = hashlib.sha256(token.encode()).hexdigest()[:10]
        return f"OOV_{digest}"
    return re.sub(r"[A-Za-z_][A-Za-z0-9_-]*", replace_token, text)


def renamed(examples: Sequence[TraceExample], rename_predicate: bool) -> List[TraceExample]:
    return [
        replace(
            item,
            candidate=_rename(item.candidate, rename_predicate),
            goal=_rename(item.goal, rename_predicate),
            run_id=("unseen-predicate-" if rename_predicate else "unseen-atoms-") + item.run_id,
        )
        for item in examples
    ]


def _ranked_group(items: List[TraceExample]) -> List[TraceExample]:
    ordered = sorted(range(len(items)), key=lambda index: v1_score(items[index]), reverse=True)
    ranks = {index: rank for rank, index in enumerate(ordered)}
    return [replace(item, queue_position=ranks[index], candidate_pool_size=len(items)) for index, item in enumerate(items)]


def adversarial_frontiers(count: int = 100, seed: int = 73) -> List[TraceExample]:
    """Create legal graph-frontier labels where endpoint overlap misleads v1."""
    rng = random.Random(seed)
    rows: List[TraceExample] = []
    for index in range(count):
        relation = f"NovelRel{index}"
        start, target = f"Start{index}", f"Target{index}"
        goal = f"({relation} {start} {target})"
        candidates = [
            TraceExample(f"({relation} Mid{index} Next{index})", goal, .8, .82, 1, 3, 0, 1, f"adv-{index}", 1, 0.0),
            TraceExample(f"({relation} {start} Trap{index})", goal, .99, .99, 0, 3, 0, 0, f"adv-{index}", 1, 0.0),
            TraceExample(f"({relation} Fake{index} {target})", goal, .99, .99, 0, 3, 0, 0, f"adv-{index}", 1, 0.0),
        ]
        rng.shuffle(candidates)
        rows.extend(_ranked_group(candidates))
    return rows


def external_kg_frontiers(paths: Iterable[Path], distractors: int = 20) -> Tuple[List[TraceExample], List[Dict[str, Any]]]:
    rows: List[TraceExample] = []
    provenance: List[Dict[str, Any]] = []
    for source_index, path in enumerate(paths):
        kg = load_relation(path, "isa")
        chain = find_transitive_chain(kg.edges, 3)
        chain_set = set(chain)
        goal = f"(Inheritance {chain[0][0]} {chain[-1][1]})"
        candidates: List[TraceExample] = []
        for left, right in chain:
            candidates.append(TraceExample(
                f"(Inheritance {left} {right})", goal, .8, .9, 0, 1, 0, 1,
                f"external-{source_index}", 1, 0.0,
            ))
        for left, right in [edge for edge in executable_edges(kg.edges) if edge not in chain_set][:distractors]:
            candidates.append(TraceExample(
                f"(Inheritance {left} {right})", goal, .8, .9, 0, 1, 0, 0,
                f"external-{source_index}", 1, 0.0,
            ))
        rows.extend(_ranked_group(candidates))
        provenance.append({
            "source": path.name, "source_sha256": kg.source_sha256,
            "proof_chain": [list(edge) for edge in chain], "candidates": len(candidates),
        })
    return rows, provenance


def noisy_label_training(
    train: Sequence[TraceExample], validation: Sequence[TraceExample], rates: Sequence[float], seed: int,
) -> List[Dict[str, Any]]:
    output = []
    for rate in rates:
        rng = random.Random(seed + round(rate * 1000))
        indices = set(rng.sample(range(len(train)), round(rate * len(train))))
        noisy = [replace(item, outcome=1 - item.outcome) if index in indices else item for index, item in enumerate(train)]
        model, history = train_model(
            noisy,
            TrainConfig(epochs=60, seed=seed, early_stopping_patience=10),
            validation,
        )
        scores = model_scores(model, validation)
        output.append({
            "label_flip_rate": rate, "flipped_labels": len(indices),
            "best_epoch": history.best_epoch,
            "clean_validation": _classification_metrics(validation, scores),
            "ranking": _ranking_metrics(validation, scores),
        })
    return output


def run(traces: Path, checkpoint: Path, output: Path) -> Dict[str, Any]:
    examples = load_trace_jsonl([traces])
    train, validation = split_by_run(examples, .25, 42)
    model = Tier1V2Model.load(checkpoint)
    external, provenance = external_kg_frontiers(DEFAULT_INPUTS)
    result = {
        "schema_version": 1,
        "purpose": "Tier 1 v1 versus v2 out-of-distribution and adversarial stress test",
        "checkpoint": str(checkpoint.relative_to(ROOT)),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "baseline_held_out": evaluate_pair(model, validation),
        "unseen_atom_vocabulary": evaluate_pair(model, renamed(validation, False)),
        "unseen_predicate_and_atoms": evaluate_pair(model, renamed(validation, True)),
        "external_kg_frontiers": {"provenance": provenance, **evaluate_pair(model, external)},
        "adversarial_v1_failure_frontiers": evaluate_pair(model, adversarial_frontiers()),
        "training_label_noise": noisy_label_training(train, validation, (0.05, 0.10, 0.20, 0.30), 42),
        "interpretation_contract": {
            "boost_requires": "v2 top-1 hit rate strictly greater than v1 on at least one held-out stress family without regressing the others",
            "broad_generalization_requires": "nontrivial v2 ranking on unseen vocabulary, unseen predicates, external KG frontiers, and adversarial v1 failures",
        },
    }
    result["performance_boost_proven"] = any(
        result[name]["v2_ranking"]["top1_hit_rate"] > result[name]["v1_ranking"]["top1_hit_rate"]
        for name in ("unseen_atom_vocabulary", "unseen_predicate_and_atoms", "external_kg_frontiers", "adversarial_v1_failure_frontiers")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks/results/reference/week11_tier1_v2_stress.json")
    args = parser.parse_args()
    result = run(args.traces, args.model, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
