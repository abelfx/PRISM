"""
Forward candidate expansion for PRISM search.

Parses Sentences, asks live `PLN.Apply` for legal one-step conclusions, and
updates task/belief buffers. Truth-value arithmetic lives in lib_pln.metta.
"""

from dataclasses import dataclass
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedSentence:
    """
    Structured representation of a relational Sentence for forward inference.

    Attributes
    ----------
    relation : str
        Predicate name, e.g. 'Inheritance' or 'Similarity'.
    subject : str
        Source concept node.
    object_node : str
        Target concept node.
    strength : float
        Truth value strength parameter in [0.0, 1.0].
    confidence : float
        Truth value confidence parameter in [0.0, 1.0].
    evidence_stamp : Tuple[str, ...]
        Tuple of premise indices contributing to this belief.
    raw : Any
        Original S-expression or string representation.
    """

    relation: str
    subject: str
    object_node: str
    strength: float
    confidence: float
    evidence_stamp: Tuple[str, ...]
    raw: Any


def parse_sentence(sentence: Any) -> Optional[ParsedSentence]:
    """
    Parse an S-expression list or string into a structured ParsedSentence.

    Inputs:
        sentence (Any): Sentence representation (list or string).

    Outputs:
        Optional[ParsedSentence]: Parsed dataclass, or None if not relational.

    What it does NOT handle:
        Does not validate semantic soundness or perform ontological reasoning.
    """
    if sentence is None:
        return None

    # Handle raw 3-element statement list: ['Inheritance', 'A', 'B']
    if isinstance(sentence, (list, tuple)) and len(sentence) == 3 and isinstance(sentence[0], str):
        if sentence[0] in {"Inheritance", "Similarity", "Implication", "Evaluation", "Member"}:
            return ParsedSentence(
                relation=str(sentence[0]),
                subject=str(sentence[1]),
                object_node=str(sentence[2]),
                strength=1.0,
                confidence=0.9,
                evidence_stamp=(),
                raw=sentence,
            )

    # Handle Python list / tuple representation:
    # ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.9]], ['1']]
    if isinstance(sentence, (list, tuple)) and len(sentence) >= 2:
        try:
            body = sentence[1]
            if isinstance(body, (list, tuple)) and len(body) >= 2:
                term = body[0]
                stv = body[1]
                if isinstance(term, (list, tuple)) and len(term) >= 3:
                    rel = str(term[0])
                    sub = str(term[1])
                    obj = str(term[2])
                    s = 1.0
                    c = 0.9
                    if isinstance(stv, (list, tuple)) and len(stv) >= 3:
                        s = float(stv[1])
                        c = float(stv[2])
                    stamp: Tuple[str, ...] = ()
                    if len(sentence) >= 3 and isinstance(sentence[2], (list, tuple)):
                        stamp = tuple(str(x) for x in sentence[2])
                    return ParsedSentence(
                        relation=rel,
                        subject=sub,
                        object_node=obj,
                        strength=s,
                        confidence=c,
                        evidence_stamp=stamp,
                        raw=sentence,
                    )
        except (IndexError, ValueError, TypeError):
            pass

    # Handle string representation: (Sentence ((Inheritance A B) (stv 0.9 0.9)) (1))
    text = str(sentence).strip()
    match = re.search(
        r"\(Sentence\s+\(\(([A-Za-z0-9_\-]+)\s+([A-Za-z0-9_\-]+)\s+([A-Za-z0-9_\-]+)\)\s+\(stv\s+([\d\.\-eE]+)\s+([\d\.\-eE]+)\)\)\s+\((.*?)\)\)",
        text,
    )
    if match:
        rel = match.group(1)
        sub = match.group(2)
        obj = match.group(3)
        s = float(match.group(4))
        c = float(match.group(5))
        ev_str = match.group(6).strip()
        stamp = tuple(ev_str.split()) if ev_str else ()
        return ParsedSentence(
            relation=rel,
            subject=sub,
            object_node=obj,
            strength=s,
            confidence=c,
            evidence_stamp=stamp,
            raw=sentence,
        )

    # Simpler pattern fallback
    match_simple = re.search(
        r"\(([A-Za-z0-9_\-]+)\s+([A-Za-z0-9_\-]+)\s+([A-Za-z0-9_\-]+)\)", text
    )
    if match_simple:
        rel = match_simple.group(1)
        if rel in {"Inheritance", "Similarity", "Implication"}:
            return ParsedSentence(
                relation=rel,
                subject=match_simple.group(2),
                object_node=match_simple.group(3),
                strength=0.9,
                confidence=0.9,
                evidence_stamp=(),
                raw=sentence,
            )

    return None


def generate_forward_candidates(
    tasks: Sequence[Any],
    beliefs: Sequence[Any],
    goal: Any = None,
    use_stage0: bool = False,
    task_selection_k: int = 3,
    concept_stvs: Optional[Dict[str, Tuple[float, float]]] = None,
) -> List[Any]:
    """
    Generate all valid 1-step forward PLN candidates between tasks and beliefs.

    Each pair is applied with live `PLN.Apply` in `lib_pln.metta`.
    `PLN.Apply` already tries both `|-` directions, so each pair is sent once.
    """
    from prism.adapters.petta.runtime import apply_pln_pair, infer_concept_stvs

    stvs = dict(concept_stvs or {})
    if not stvs:
        stvs = infer_concept_stvs(list(tasks) + list(beliefs))
    else:
        inferred = infer_concept_stvs(list(tasks) + list(beliefs))
        for name, tv in inferred.items():
            stvs.setdefault(name, tv)

    parsed_tasks: List[ParsedSentence] = []
    for t in tasks:
        p = parse_sentence(t)
        if p:
            parsed_tasks.append(p)

    parsed_beliefs: List[ParsedSentence] = []
    for b in beliefs:
        p = parse_sentence(b)
        if p:
            parsed_beliefs.append(p)

    candidates: List[Any] = []
    seen_conclusions: Set[str] = set()

    # Form existing belief signatures to prevent re-deriving existing knowledge
    existing_sigs: Set[str] = {
        f"{b.relation}:{b.subject}:{b.object_node}:{','.join(b.evidence_stamp)}"
        for b in parsed_beliefs
    }

    def consider(p1: ParsedSentence, p2: ParsedSentence) -> None:
        result = apply_pln_pair(p1, p2, stvs)
        if not result:
            return
        parsed = parse_sentence(result)
        if not parsed:
            return
        sig = (
            f"{parsed.relation}:{parsed.subject}:{parsed.object_node}:"
            f"{','.join(parsed.evidence_stamp)}"
        )
        if sig not in existing_sigs and sig not in seen_conclusions:
            seen_conclusions.add(sig)
            candidates.append(result)

    if use_stage0 and goal is not None:
        from prism.stage0 import extract_concepts, filter_beliefs

        goal_concepts = extract_concepts(goal)
        # Select tasks that are either derived lemmas (depth >= 1) or share concepts with goal
        connected_tasks = [
            t
            for t in parsed_tasks
            if len(t.evidence_stamp) >= 2 or bool(extract_concepts(t.raw) & goal_concepts)
        ]
        if not connected_tasks:
            connected_tasks = parsed_tasks

        for t in connected_tasks:
            try:
                filtered_raw = filter_beliefs(t.raw, goal, beliefs)
                if not filtered_raw:
                    raise ValueError("Stage 0 returned no usable premises")
            except Exception as exc:
                logger.warning("stage0_full_belief_fallback: %s", exc)
                filtered_raw = list(beliefs)
            filtered_parsed = [
                p for p in (parse_sentence(b) for b in filtered_raw if b) if p
            ]
            for b in filtered_parsed:
                consider(t, b)
    else:
        for t in parsed_tasks:
            for b in parsed_beliefs:
                consider(t, b)

    return candidates


def apply_candidate(
    candidate: Any,
    tasks: Sequence[Any],
    beliefs: Sequence[Any],
) -> Tuple[List[Any], List[Any]]:
    """
    Apply a derived candidate sentence, producing updated tasks and belief buffers.

    Inputs:
        candidate (Any): Newly derived Sentence.
        tasks (Sequence[Any]): Current tasks.
        beliefs (Sequence[Any]): Current beliefs.

    Outputs:
        Tuple[List[Any], List[Any]]: (new_tasks, new_beliefs).

    What it does NOT handle:
        Does not enforce maximum queue size limits (handled by search engine).
    """
    new_beliefs = list(beliefs)
    new_beliefs.append(candidate)

    new_tasks = list(tasks)
    new_tasks.append(candidate)

    return new_tasks, new_beliefs
