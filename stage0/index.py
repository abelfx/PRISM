"""
PRISM Stage 0 Indexed Premise Pre-Filter.

Provides concept-based premise indexing and candidate-premise pre-filtering
for PLN derivation loops (§4). Filters the active belief buffer so that
MeTTa's derivation engine only evaluates beliefs that share concepts with the
selected task or goal.
"""

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from prism.core.config import DEFAULT_CONFIG, Stage0Config

# Standard keywords in PLN / MeTTa expressions that should not be treated as domain concepts
STRUCTURAL_KEYWORDS: Set[str] = {
    "Sentence",
    "stv",
    "Concept",
    "Predicate",
    "List",
    "Inheritance",
    "Implication",
    "Evaluation",
    "Similarity",
    "Equivalence",
    "Not",
    "Member",
}


def extract_concepts(expr: Any) -> Set[str]:
    """
    Recursively extract domain concept identifiers from any nested structure.

    Inputs:
        expr (Any): Nested list, tuple, or string representation of a MeTTa term.

    Outputs:
        Set[str]: Set of domain concept names, excluding numbers and structural keywords.

    What it does NOT handle:
        Does not resolve logic variables, does not unify terms, and does not check types.
    """
    if isinstance(expr, (int, float)):
        return set()
    if isinstance(expr, str):
        tokens = re.findall(r"[A-Za-z0-9_\-]+", expr)
        return {
            t
            for t in tokens
            if not re.match(r"^-?\d+(\.\d+)?$", t)
            and t not in STRUCTURAL_KEYWORDS
        }
    if isinstance(expr, (list, tuple)):
        concepts: Set[str] = set()
        for sub in expr:
            concepts |= extract_concepts(sub)
        return concepts
    return set()


def extract_statement_components(sentence: Any) -> Tuple[Optional[str], Set[str]]:
    """
    Extract the relational link type and concept atoms from a Sentence structure.

    Inputs:
        sentence (Any): Sentence representation [Sentence, [statement, stv], stamp].

    Outputs:
        Tuple[Optional[str], Set[str]]: (link_type, set_of_concept_atoms).
        link_type is None if not an atomic relation.

    What it does NOT handle:
        Does not resolve logic variables, does not execute unifications,
        and does not evaluate truth values.
    """
    try:
        statement = None
        if isinstance(sentence, (list, tuple)) and len(sentence) >= 2:
            body = sentence[1]
            if isinstance(body, (list, tuple)) and len(body) >= 1:
                statement = body[0]
        if statement is None:
            statement = sentence

        link_type = None
        if isinstance(statement, (list, tuple)) and len(statement) >= 1:
            link_type = str(statement[0])
        elif isinstance(statement, str):
            tokens = re.findall(r"[A-Za-z0-9_\-]+", statement)
            if tokens:
                link_type = tokens[0]

        concepts = extract_concepts(statement)
        return link_type, concepts
    except (IndexError, TypeError, ValueError):
        return None, set()


class PremiseIndex:
    """
    Structural premise index mapping (link_type, concept) and concept -> sentences.

    Inputs:
        config (Stage0Config): Configuration settings for Stage 0.

    Outputs:
        Index instance capable of fast candidate and goal lookups.

    What it does NOT handle:
        Does not perform MeTTa FFI conversions or mutate input sentence collections.
    """

    def __init__(self, config: Stage0Config = DEFAULT_CONFIG.stage0) -> None:
        self.config = config
        self._by_link_concept: Dict[Tuple[str, str], List[Any]] = defaultdict(list)
        self._by_concept: Dict[str, List[Any]] = defaultdict(list)
        self._all_sentences: List[Any] = []

    def clear(self) -> None:
        """Clear all indexed beliefs."""
        self._by_link_concept.clear()
        self._by_concept.clear()
        self._all_sentences.clear()

    def add(self, sentence: Any) -> None:
        """
        Add a single sentence to the structural index.

        Inputs:
            sentence (Any): Sentence representation.

        Outputs:
            None.

        What it does NOT handle:
            Does not check for duplicates or validate truth values.
        """
        link_type, concepts = extract_statement_components(sentence)
        self._all_sentences.append(sentence)
        for c in concepts:
            self._by_concept[c].append(sentence)
            if link_type:
                self._by_link_concept[(link_type, c)].append(sentence)

    def lookup_by_goal(self, goal: Any) -> List[Any]:
        """
        Retrieve beliefs sharing concepts with the goal expression (§4).

        Inputs:
            goal (Any): Goal expression (e.g. ['Inheritance', 'A', 'F']).

        Outputs:
            List[Any]: List of matching sentences (preserves insertion order, deduplicated).

        What it does NOT handle:
            Does not evaluate intermediate proof steps.
        """
        goal_concepts = extract_concepts(goal)
        if not goal_concepts:
            return list(self._all_sentences)

        seen = set()
        results: List[Any] = []
        for c in goal_concepts:
            for s in self._by_concept.get(c, []):
                s_id = id(s)
                if s_id not in seen:
                    seen.add(s_id)
                    results.append(s)
        return results

    def filter_beliefs(
        self,
        candidate: Any,
        goal: Any,
        beliefs: List[Any],
    ) -> List[Any]:
        """
        Filter beliefs to only those relevant to candidate task and/or goal.

        Inputs:
            candidate (Any): Current selected Sentence task (or None).
            goal (Any): Derivation goal term (or None / empty).
            beliefs (List[Any]): Full buffer of current beliefs.

        Outputs:
            List[Any]: Filtered subset of beliefs.

        What it does NOT handle:
            Does not execute rule deductions or alter truth values.
        """
        if not beliefs:
            return []

        # Check if goal or candidate is provided
        has_candidate = candidate is not None and candidate != () and candidate != "()" and candidate != []
        has_goal = goal is not None and goal != () and goal != "()" and goal != []

        if not has_candidate and not has_goal:
            return list(beliefs)

        target_concepts: Set[str] = set()
        if has_candidate:
            target_concepts |= extract_concepts(candidate)
        if has_goal:
            target_concepts |= extract_concepts(goal)

        # If no concept atoms found in candidate or goal, fallback to all beliefs
        if not target_concepts:
            return list(beliefs)

        filtered: List[Any] = []
        seen = set()
        for b in beliefs:
            b_id = id(b)
            if b_id in seen:
                continue
            b_concepts = extract_concepts(b)
            # Retain if shares a concept with candidate/goal, OR if has no concept (generic rule)
            if not b_concepts or (b_concepts & target_concepts):
                seen.add(b_id)
                filtered.append(b)

        # Safe fallback: if filtering yielded nothing, return all beliefs to prevent derivation stall
        if not filtered:
            return list(beliefs)

        return filtered
