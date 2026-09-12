"""
Forward Derivation Rules and Candidate Expansion for PRISM Search.

Implements structural deduction rules (Inheritance transitivity, Similarity transitivity)
with PLN truth-value calculation and cyclic evidence prevention.
"""

from dataclasses import dataclass
import re
from typing import Any, List, Optional, Sequence, Set, Tuple


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


def deduce_pair(p1: ParsedSentence, p2: ParsedSentence) -> Optional[Any]:
    """
    Attempt deduction between two sentences if they form a transitive chain.

    Conditions:
        1. p1.object_node == p2.subject (or symmetric match if Similarity).
        2. Evidence stamps are disjoint (prevents circular evidence loops).

    Inputs:
        p1 (ParsedSentence): First premise.
        p2 (ParsedSentence): Second premise.

    Outputs:
        Optional[Any]: Derived conclusion Sentence in list format, or None.

    What it does NOT handle:
        Does not check truth value revision with preexisting identical conclusions.
    """
    # Prevent trivial self-loops (A -> A)
    if p1.subject == p2.object_node:
        return None

    # Check transitive link: (Rel1 A B) and (Rel2 B C)
    if p1.object_node == p2.subject:
        sub = p1.subject
        obj = p2.object_node
    elif p1.relation == "Similarity" and p1.subject == p2.subject:
        # (Similarity B A) rewritten as (Similarity A B)
        sub = p1.object_node
        obj = p2.object_node
    else:
        return None

    # Enforce evidence disjointness
    stamp1 = set(p1.evidence_stamp)
    stamp2 = set(p2.evidence_stamp)
    if stamp1 and stamp2 and not stamp1.isdisjoint(stamp2):
        return None

    # Determine output relation
    if p1.relation == "Similarity" and p2.relation == "Similarity":
        out_rel = "Similarity"
    else:
        out_rel = "Inheritance"

    # Compute conclusion STV
    s = round(p1.strength * p2.strength, 4)
    c = round(p1.confidence * p2.confidence * p1.strength, 4)

    # Combine evidence stamps deterministically
    combined_stamp = sorted(list(stamp1 | stamp2))

    return ["Sentence", [[out_rel, sub, obj], ["stv", s, c]], combined_stamp]


def generate_forward_candidates(
    tasks: Sequence[Any],
    beliefs: Sequence[Any],
) -> List[Any]:
    """
    Generate all valid 1-step forward deduction candidates between tasks and beliefs.

    Inputs:
        tasks (Sequence[Any]): Active task queue.
        beliefs (Sequence[Any]): Known beliefs.

    Outputs:
        List[Any]: List of newly derivable candidate sentences.

    What it does NOT handle:
        Does not filter candidates against the goal or evaluate heuristic scores.
    """
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

    # Deduce between active tasks and beliefs
    for t in parsed_tasks:
        for b in parsed_beliefs:
            # Direction 1: task -> belief
            res1 = deduce_pair(t, b)
            if res1:
                parsed_res1 = parse_sentence(res1)
                if parsed_res1:
                    sig1 = f"{parsed_res1.relation}:{parsed_res1.subject}:{parsed_res1.object_node}:{','.join(parsed_res1.evidence_stamp)}"
                    if sig1 not in existing_sigs and sig1 not in seen_conclusions:
                        seen_conclusions.add(sig1)
                        candidates.append(res1)

            # Direction 2: belief -> task
            res2 = deduce_pair(b, t)
            if res2:
                parsed_res2 = parse_sentence(res2)
                if parsed_res2:
                    sig2 = f"{parsed_res2.relation}:{parsed_res2.subject}:{parsed_res2.object_node}:{','.join(parsed_res2.evidence_stamp)}"
                    if sig2 not in existing_sigs and sig2 not in seen_conclusions:
                        seen_conclusions.add(sig2)
                        candidates.append(res2)

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
