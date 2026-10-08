"""Hand-written OOD, minimal-contrast and confidence probes for Tier 1 v2.

The examples in this file are intentionally authored independently of the
synthetic trace generators.  They test the frozen checkpoint only; no fitting
or threshold tuning is performed here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from prism.training.dataset import TraceExample, load_trace_jsonl, split_by_run
from prism.training.model import Tier1V2Model


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "artifacts/models/tier1_v2.npz"
DEFAULT_OUTPUT = ROOT / "benchmarks/results/reference/week11_tier1_v2_manual_probes.json"
DEFAULT_TRACES = ROOT / "artifacts/training/week11_traces.jsonl"


@dataclass(frozen=True)
class Probe:
    probe_id: str
    candidate: str
    goal: str
    label: int
    category: str
    valid_pln_shape: bool = True
    note: str = ""


OOD_PROBES: Tuple[Probe, ...] = (
    Probe("ood-01", "(Inheritance kestrel raptor)", "(Inheritance kestrel animal)", 1, "unseen-taxonomy"),
    Probe("ood-02", "(Inheritance salmon fish)", "(Inheritance salmon organism)", 1, "unseen-taxonomy"),
    Probe("ood-03", "(Implication fever dehydration)", "(Implication infection dehydration)", 1, "unseen-predicate"),
    Probe("ood-04", "(Similarity sedan automobile)", "(Similarity sedan vehicle)", 1, "synonym"),
    Probe("ood-05", "(Evaluation (Predicate edible) (List mushroom))", "(Evaluation (Predicate edible) (List mushroom))", 1, "nested-exact"),
    Probe("ood-06", "(Member cobalt transition-metal)", "(Inheritance cobalt element)", 1, "unseen-relation"),
    Probe("ood-07", "(Inheritance solar-panel energy-device)", "(Inheritance solar-panel technology)", 1, "hyphenated-atoms"),
    Probe("ood-08", "(Implication rainfall soil-moisture)", "(Implication monsoon soil-moisture)", 1, "alternate-cause"),
    Probe("ood-09", "(Similarity physician doctor)", "(Similarity physician professional)", 1, "synonym"),
    Probe("ood-10", "(Inheritance oak tree)", "(Inheritance oak organism)", 1, "unseen-taxonomy"),
    Probe("ood-11", "(Inheritance kestrel kitchen-appliance)", "(Inheritance kestrel animal)", 0, "semantic-distractor"),
    Probe("ood-12", "(Inheritance salmon mountain)", "(Inheritance salmon organism)", 0, "semantic-distractor"),
    Probe("ood-13", "(Implication fever snowfall)", "(Implication infection dehydration)", 0, "semantic-distractor"),
    Probe("ood-14", "(Similiarity sedan automobile)", "(Similarity sedan vehicle)", 0, "typo", False, "Misspelled relation; should be rejected before scoring."),
    Probe("ood-15", "(Not (Evaluation (Predicate edible) (List mushroom)))", "(Evaluation (Predicate edible) (List mushroom))", 0, "negation"),
    Probe("ood-16", "(Member cobalt fruit)", "(Inheritance cobalt element)", 0, "semantic-distractor"),
    Probe("ood-17", "(Inheritance solar-panel reptile)", "(Inheritance solar-panel technology)", 0, "semantic-distractor"),
    Probe("ood-18", "(Implication rainfall keyboard)", "(Implication monsoon soil-moisture)", 0, "semantic-distractor"),
    Probe("ood-19", "(Similarity physician volcano)", "(Similarity physician professional)", 0, "semantic-distractor"),
    Probe("ood-20", "(Inheritence oak tree)", "(Inheritance oak organism)", 0, "typo", False, "Misspelled relation; should be rejected before scoring."),
)


CONTRAST_PAIRS: Tuple[Tuple[Probe, Probe], ...] = (
    (Probe("contrast-01-positive", "(Inheritance robin bird)", "(Inheritance robin animal)", 1, "contrast"), Probe("contrast-01-negative", "(Inheritance robin vehicle)", "(Inheritance robin animal)", 0, "contrast")),
    (Probe("contrast-02-positive", "(Implication smoke fire)", "(Implication smoke hazard)", 1, "contrast"), Probe("contrast-02-negative", "(Implication smoke snow)", "(Implication smoke hazard)", 0, "contrast")),
    (Probe("contrast-03-positive", "(Similarity kitten cat)", "(Similarity kitten mammal)", 1, "contrast"), Probe("contrast-03-negative", "(Similarity kitten mineral)", "(Similarity kitten mammal)", 0, "contrast")),
    (Probe("contrast-04-positive", "(Evaluation (Predicate safe) medicine)", "(Evaluation (Predicate safe) treatment)", 1, "contrast"), Probe("contrast-04-negative", "(Evaluation (Predicate unsafe) medicine)", "(Evaluation (Predicate safe) treatment)", 0, "contrast")),
    (Probe("contrast-05-positive", "(Member copper metal)", "(Inheritance copper element)", 1, "contrast"), Probe("contrast-05-negative", "(Member copper mammal)", "(Inheritance copper element)", 0, "contrast")),
    (Probe("contrast-06-positive", "(Inheritance antibiotic medicine)", "(Inheritance antibiotic treatment)", 1, "contrast"), Probe("contrast-06-negative", "(Inheritance antibiotic vehicle)", "(Inheritance antibiotic treatment)", 0, "contrast")),
    (Probe("contrast-07-positive", "(Implication exercise fitness)", "(Implication exercise health)", 1, "contrast"), Probe("contrast-07-negative", "(Implication exercise corrosion)", "(Implication exercise health)", 0, "contrast")),
    (Probe("contrast-08-positive", "(Similarity laptop computer)", "(Similarity laptop device)", 1, "contrast"), Probe("contrast-08-negative", "(Similarity laptop vegetable)", "(Similarity laptop device)", 0, "contrast")),
    (Probe("contrast-09-positive", "(Inheritance tulip flower)", "(Inheritance tulip plant)", 1, "contrast"), Probe("contrast-09-negative", "(Inheritance tulip machine)", "(Inheritance tulip plant)", 0, "contrast")),
    (Probe("contrast-10-positive", "(Implication ice cold)", "(Implication ice slippery)", 1, "contrast"), Probe("contrast-10-negative", "(Implication ice hot)", "(Implication ice slippery)", 0, "contrast")),
)


def as_example(probe: Probe) -> TraceExample:
    return TraceExample(
        candidate=probe.candidate,
        goal=probe.goal,
        strength=0.8,
        confidence=0.8,
        depth=1,
        candidate_pool_size=2,
        queue_position=0,
        outcome=probe.label,
        run_id=probe.probe_id,
        step=1,
        heuristic_score=0.0,
    )


def score_probe(model: Tier1V2Model, probe: Probe) -> Dict[str, Any]:
    example = as_example(probe)
    probability = float(model.predict_examples([example])[0])
    prediction = int(probability >= 0.5)
    candidate_tokens = example.candidate_tokens
    goal_tokens = example.goal_tokens
    all_tokens = (*candidate_tokens, *goal_tokens)
    unknown = [token for token in all_tokens if token not in model.token_to_id]
    confidence = probability if prediction == 1 else 1.0 - probability
    return {
        **asdict(probe),
        "probability_positive": probability,
        "prediction": prediction,
        "correct": prediction == probe.label,
        "prediction_confidence": confidence,
        "unknown_token_fraction": len(unknown) / max(1, len(all_tokens)),
        "unknown_tokens": sorted(set(unknown)),
    }


def score_example(model: Tier1V2Model, example: TraceExample) -> Dict[str, Any]:
    """Score a trace example while exposing vocabulary coverage."""
    probability = float(model.predict_examples([example])[0])
    all_tokens = (*example.candidate_tokens, *example.goal_tokens)
    unknown = [token for token in all_tokens if token not in model.token_to_id]
    return {
        "probability_positive": probability,
        "prediction": int(probability >= 0.5),
        "unknown_token_fraction": len(unknown) / max(1, len(all_tokens)),
        "unknown_tokens": sorted(set(unknown)),
    }


def grounded_contrast_sets(model: Tier1V2Model, traces: Path) -> Dict[str, Any]:
    """Find naturally occurring one-token label flips in the held-out split.

    These pairs keep the run, step, goal and numeric context fixed.  The only
    candidate-token difference is one atom replacement, and the recorded proof
    trace label flips from on-path to off-path.
    """
    examples = load_trace_jsonl([traces])
    _, validation = split_by_run(examples, validation_fraction=0.25, seed=42)
    groups: Dict[Tuple[str, int, str], List[TraceExample]] = defaultdict(list)
    for example in validation:
        groups[(example.run_id, example.step, example.goal)].append(example)

    rows: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()
    for (run_id, step, goal), group in groups.items():
        positives = [item for item in group if item.outcome == 1]
        negatives = [item for item in group if item.outcome == 0]
        for positive in positives:
            for negative in negatives:
                positive_tokens = set(positive.candidate_tokens)
                negative_tokens = set(negative.candidate_tokens)
                removed = positive_tokens - negative_tokens
                added = negative_tokens - positive_tokens
                if len(removed) != 1 or len(added) != 1:
                    continue
                identity = (positive.candidate, negative.candidate, goal)
                if identity in seen:
                    continue
                seen.add(identity)
                pos_score = score_example(model, positive)
                neg_score = score_example(model, negative)
                rows.append({
                    "run_id": run_id,
                    "step": step,
                    "goal": goal,
                    "positive_candidate": positive.candidate,
                    "negative_candidate": negative.candidate,
                    "single_token_change": {
                        "removed": next(iter(removed)),
                        "added": next(iter(added)),
                    },
                    "positive_probability": pos_score["probability_positive"],
                    "negative_probability": neg_score["probability_positive"],
                    "probability_delta": pos_score["probability_positive"] - neg_score["probability_positive"],
                    "prediction_flipped": pos_score["prediction"] == 1 and neg_score["prediction"] == 0,
                    "probability_direction_correct": pos_score["probability_positive"] > neg_score["probability_positive"],
                    "positive_unknown_fraction": pos_score["unknown_token_fraction"],
                    "negative_unknown_fraction": neg_score["unknown_token_fraction"],
                })

    return {
        "source": str(traces.relative_to(ROOT)),
        "split": "held-out runs (validation_fraction=0.25, seed=42)",
        "pairs": len(rows),
        "note": "Only unique, naturally occurring pairs with exactly one candidate-token replacement are reported; the held-out traces contain two.",
        "hard_label_flip_rate": sum(row["prediction_flipped"] for row in rows) / max(1, len(rows)),
        "probability_direction_accuracy": sum(row["probability_direction_correct"] for row in rows) / max(1, len(rows)),
        "mean_probability_delta": sum(row["probability_delta"] for row in rows) / max(1, len(rows)),
        "cases": rows,
    }


def summarize(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    valid = [row for row in rows if row["valid_pln_shape"]]
    errors = [row for row in valid if not row["correct"]]
    invalid = [row for row in rows if not row["valid_pln_shape"]]
    return {
        "all_inputs": len(rows),
        "valid_pln_inputs": len(valid),
        "invalid_or_typo_inputs": len(invalid),
        "accuracy_on_valid_inputs": sum(row["correct"] for row in valid) / max(1, len(valid)),
        "accuracy_if_invalid_inputs_are_expected_negative": sum(row["correct"] for row in rows) / max(1, len(rows)),
        "mean_prediction_confidence_on_valid_inputs": sum(row["prediction_confidence"] for row in valid) / max(1, len(valid)),
        "mean_unknown_token_fraction": sum(row["unknown_token_fraction"] for row in rows) / max(1, len(rows)),
        "overconfident_errors_at_0_90": sum(row["prediction_confidence"] >= 0.9 for row in errors),
        "errors": len(errors),
    }


def run(checkpoint: Path, traces: Path, output: Path) -> Dict[str, Any]:
    model = Tier1V2Model.load(checkpoint)
    ood_rows = [score_probe(model, probe) for probe in OOD_PROBES]
    contrast_rows: List[Dict[str, Any]] = []
    flips = 0
    directional = 0
    for positive, negative in CONTRAST_PAIRS:
        pos = score_probe(model, positive)
        neg = score_probe(model, negative)
        predicted_flip = pos["prediction"] == 1 and neg["prediction"] == 0
        probability_direction_correct = pos["probability_positive"] > neg["probability_positive"]
        flips += int(predicted_flip)
        directional += int(probability_direction_correct)
        contrast_rows.append({
            "pair_id": positive.probe_id.replace("-positive", ""),
            "changed_from": positive.candidate,
            "changed_to": negative.candidate,
            "goal": positive.goal,
            "positive_probability": pos["probability_positive"],
            "negative_probability": neg["probability_positive"],
            "prediction_flipped": predicted_flip,
            "probability_direction_correct": probability_direction_correct,
            "positive_unknown_fraction": pos["unknown_token_fraction"],
            "negative_unknown_fraction": neg["unknown_token_fraction"],
        })

    all_valid_rows = [row for row in ood_rows if row["valid_pln_shape"]]
    confidence_bins = {
        "p_below_0_01": sum(row["probability_positive"] < 0.01 for row in all_valid_rows),
        "p_0_01_to_0_10": sum(0.01 <= row["probability_positive"] < 0.10 for row in all_valid_rows),
        "p_0_10_to_0_90": sum(0.10 <= row["probability_positive"] <= 0.90 for row in all_valid_rows),
        "p_0_90_to_0_99": sum(0.90 < row["probability_positive"] <= 0.99 for row in all_valid_rows),
        "p_above_0_99": sum(row["probability_positive"] > 0.99 for row in all_valid_rows),
    }
    result = {
        "schema_version": 2,
        "purpose": "hand-written OOD, one-token contrast and confidence probes",
        "checkpoint": str(checkpoint.relative_to(ROOT)),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "fixed_numeric_features": {
            "strength": 0.8,
            "confidence": 0.8,
            "depth": 1,
            "candidate_pool_size": 2,
            "queue_position": 0,
        },
        "ood": {"summary": summarize(ood_rows), "cases": ood_rows},
        "contrast_sets": {
            "pairs": len(contrast_rows),
            "hard_label_flip_rate": flips / len(contrast_rows),
            "probability_direction_accuracy": directional / len(contrast_rows),
            "cases": contrast_rows,
        },
        "grounded_in_vocabulary_contrast_sets": grounded_contrast_sets(model, traces),
        "confidence": {
            "valid_ood_probability_bins": confidence_bins,
            "warning": "Sigmoid values are ranking scores, not calibrated semantic probabilities on OOD inputs.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.model, args.traces, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
