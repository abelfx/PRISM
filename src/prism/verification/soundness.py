"""Replay PRISM proof actions through the authoritative PLN kernel."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations
import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from prism.search.rules import ParsedSentence, parse_sentence
from prism.search.state import matches_goal

ApplyFunction = Callable[[Any, Any, Optional[Dict[str, Tuple[float, float]]]], Optional[Any]]


@dataclass(frozen=True)
class VerificationFailure:
    """First reason a proof failed independent replay."""

    code: str
    message: str
    step_index: Optional[int] = None


@dataclass(frozen=True)
class StepVerification:
    """Replay evidence for one recorded derived action."""

    step_index: int
    premise_indices: Tuple[int, int]
    recorded: Any
    replayed: Any
    term_match: bool
    stv_match: bool
    evidence_match: bool


@dataclass
class ProofVerificationResult:
    """Machine-readable outcome of independent proof verification."""

    valid: bool
    goal_valid: bool
    steps_recorded: int
    steps_replayed: int
    term_match: bool
    stv_match: bool
    evidence_match: bool
    steps: List[StepVerification] = field(default_factory=list)
    first_failure: Optional[VerificationFailure] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _actions(proof_path: Sequence[Any]) -> List[Any]:
    """Accept SearchNodes or a direct sequence of recorded conclusions."""
    actions: List[Any] = []
    for item in proof_path:
        action = getattr(item, "action", item)
        if action is not None:
            actions.append(action)
    return actions


def _failure(
    code: str,
    message: str,
    actions: Sequence[Any],
    steps: Sequence[StepVerification],
    *,
    step_index: Optional[int] = None,
    term_match: bool = True,
    stv_match: bool = True,
    evidence_match: bool = True,
) -> ProofVerificationResult:
    return ProofVerificationResult(
        valid=False,
        goal_valid=False,
        steps_recorded=len(actions),
        steps_replayed=len(steps),
        term_match=term_match,
        stv_match=stv_match,
        evidence_match=evidence_match,
        steps=list(steps),
        first_failure=VerificationFailure(code, message, step_index),
    )


def _same_term(left: ParsedSentence, right: ParsedSentence) -> bool:
    return (
        left.relation,
        left.subject,
        left.object_node,
    ) == (
        right.relation,
        right.subject,
        right.object_node,
    )


def _same_stv(left: ParsedSentence, right: ParsedSentence, tolerance: float) -> bool:
    return math.isclose(left.strength, right.strength, abs_tol=tolerance, rel_tol=0.0) and math.isclose(
        left.confidence, right.confidence, abs_tol=tolerance, rel_tol=0.0
    )


def verify_proof(
    initial_facts: Sequence[Any],
    proof_path: Sequence[Any],
    goal: Any,
    *,
    concept_stvs: Optional[Dict[str, Tuple[float, float]]] = None,
    tolerance: float = 1e-6,
    apply_fn: Optional[ApplyFunction] = None,
) -> ProofVerificationResult:
    """Replay every recorded action using prior premises and ``PLN.Apply``.

    No truth-value formula is implemented here.  The supplied/default kernel is
    responsible for producing the conclusion, STV, and evidence stamp.
    """
    if apply_fn is None:
        from prism.adapters.petta.runtime import apply_pln_sentences

        apply_fn = apply_pln_sentences

    if tolerance < 0 or not math.isfinite(tolerance):
        raise ValueError("tolerance must be a finite non-negative number")

    actions = _actions(proof_path)
    parsed_initial = [parse_sentence(fact) for fact in initial_facts]
    if any(parsed is None for parsed in parsed_initial):
        return _failure("invalid_initial_fact", "An initial fact is not a parseable Sentence.", actions, [])

    source_ids = {
        evidence
        for parsed in parsed_initial
        if parsed is not None
        for evidence in parsed.evidence_stamp
    }
    for parsed in parsed_initial:
        assert parsed is not None
        stamp = parsed.evidence_stamp
        if len(stamp) != len(set(stamp)):
            return _failure("circular_source_evidence", "An initial fact repeats an evidence ID.", actions, [])

    available: List[Any] = list(initial_facts)
    steps: List[StepVerification] = []

    for step_index, recorded in enumerate(actions):
        expected = parse_sentence(recorded)
        if expected is None:
            return _failure(
                "invalid_recorded_action",
                "Recorded action is not a parseable Sentence.",
                actions,
                steps,
                step_index=step_index,
            )
        if not expected.evidence_stamp:
            return _failure(
                "missing_evidence",
                "A derived action has no evidence stamp.",
                actions,
                steps,
                step_index=step_index,
                evidence_match=False,
            )
        if len(expected.evidence_stamp) != len(set(expected.evidence_stamp)):
            return _failure(
                "circular_evidence",
                "A derived action repeats evidence and therefore depends on an overlapping path.",
                actions,
                steps,
                step_index=step_index,
                evidence_match=False,
            )
        unknown = set(expected.evidence_stamp) - source_ids
        if unknown:
            return _failure(
                "unknown_evidence",
                f"Derived action contains unknown source evidence: {sorted(unknown)}.",
                actions,
                steps,
                step_index=step_index,
                evidence_match=False,
            )

        matched: Optional[StepVerification] = None
        kernel_errors: List[str] = []
        term_seen = stv_seen = False
        for (left_index, left), (right_index, right) in combinations(enumerate(available), 2):
            p_left = parse_sentence(left)
            p_right = parse_sentence(right)
            if p_left is None or p_right is None:
                continue
            if set(p_left.evidence_stamp) & set(p_right.evidence_stamp):
                continue
            for first_index, first, second_index, second in (
                (left_index, left, right_index, right),
                (right_index, right, left_index, left),
            ):
                try:
                    replayed = apply_fn(first, second, concept_stvs)
                except Exception as exc:  # kernel boundary: fail closed below
                    kernel_errors.append(str(exc))
                    continue
                actual = parse_sentence(replayed)
                if actual is None:
                    continue
                term_ok = _same_term(expected, actual)
                stv_ok = term_ok and _same_stv(expected, actual, tolerance)
                evidence_ok = stv_ok and (
                    set(actual.evidence_stamp) == set(expected.evidence_stamp)
                    == (set(p_left.evidence_stamp) | set(p_right.evidence_stamp))
                )
                term_seen = term_seen or term_ok
                stv_seen = stv_seen or stv_ok
                if term_ok and stv_ok and evidence_ok:
                    matched = StepVerification(
                        step_index=step_index,
                        premise_indices=(first_index, second_index),
                        recorded=recorded,
                        replayed=replayed,
                        term_match=True,
                        stv_match=True,
                        evidence_match=True,
                    )
                    break
            if matched is not None:
                break

        if matched is None:
            if kernel_errors:
                return _failure(
                    "kernel_error",
                    f"PLN replay failed closed: {kernel_errors[0]}",
                    actions,
                    steps,
                    step_index=step_index,
                )
            code = "unsupported_action"
            if term_seen and not stv_seen:
                code = "stv_mismatch"
            elif stv_seen:
                code = "evidence_mismatch"
            return _failure(
                code,
                "No prior disjoint premise pair reproduced the recorded action.",
                actions,
                steps,
                step_index=step_index,
                term_match=term_seen,
                stv_match=stv_seen,
                evidence_match=False,
            )

        steps.append(matched)
        available.append(recorded)

    goal_sentence = next((sentence for sentence in reversed(available) if matches_goal(sentence, goal)), None)
    if goal_sentence is None:
        return _failure("goal_not_proved", "The replayed proof does not contain the requested goal.", actions, steps)

    return ProofVerificationResult(
        valid=True,
        goal_valid=True,
        steps_recorded=len(actions),
        steps_replayed=len(steps),
        term_match=True,
        stv_match=True,
        evidence_match=True,
        steps=steps,
    )
