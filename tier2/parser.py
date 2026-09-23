"""
Subgoal Response Parser & Hallucination Guard for PRISM Tier 2.

Parses structured JSON responses from LLM backends into valid MeTTa/PLN subgoals,
enforcing relational syntax and concept grounding guards.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

VALID_RELATIONS = {
    "Inheritance",
    "Similarity",
    "Implication",
    "Evaluation",
    "Subset",
    "Member",
}


@dataclass
class SubgoalResult:
    """
    Structured outcome of an LLM subgoal generation request.

    Attributes:
        subgoal: Parsed S-expression list, e.g. ['Inheritance', 'C', 'M'].
        subgoal_str: String representation, e.g. '(Inheritance C M)'.
        suggested_premise: Optional parsed premise expression.
        suggested_premise_str: Optional string representation of premise.
        reasoning: Text rationale provided by the model.
        raw_json: Parsed dictionary payload from model output.
    """
    subgoal: List[Any]
    subgoal_str: str
    suggested_premise: Optional[List[Any]] = None
    suggested_premise_str: Optional[str] = None
    reasoning: str = ""
    raw_json: Optional[Dict[str, Any]] = None


def parse_s_expression(expr_str: str) -> Optional[List[str]]:
    """
    Parse a string S-expression into a list of token strings.
    E.g., '(Inheritance A B)' -> ['Inheritance', 'A', 'B'].
    """
    cleaned = expr_str.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    if len(tokens) >= 3:
        return tokens
    return None


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Locate and decode JSON content within text, handling markdown fences.
    """
    if not text or not text.strip():
        return None

    # Check for markdown fenced JSON: ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Find the outermost curly braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass

    return None


def parse_subgoal_response(
    response_text: str,
    domain_concepts: Optional[Set[str]] = None,
    active_goal: Optional[Any] = None,
) -> Optional[SubgoalResult]:
    """
    Extract, validate, and guard an intermediate subgoal from LLM response.

    Args:
        response_text: Raw string response returned by LLM client.
        domain_concepts: Set of known atomic concepts present in the environment.
        active_goal: The current query goal to guard against trivial self-proposals.

    Returns:
        SubgoalResult if valid and grounded, else None.
    """
    data = extract_json_from_text(response_text)
    if not data or not isinstance(data, dict):
        return None

    subgoal_raw = data.get("subgoal")
    if not subgoal_raw or not isinstance(subgoal_raw, str):
        return None

    subgoal_tokens = parse_s_expression(subgoal_raw)
    if not subgoal_tokens:
        return None

    rel, sub, obj = subgoal_tokens[0], subgoal_tokens[1], subgoal_tokens[2]

    # 1. Relation Syntax Guard: must be a known logical relation
    if rel not in VALID_RELATIONS:
        return None

    # 2. Trivial Goal Guard: subgoal must not be identical to active goal
    if active_goal:
        from prism.search.rules import parse_sentence

        parsed_goal = parse_sentence(active_goal)
        if parsed_goal:
            if (
                parsed_goal.relation == rel
                and parsed_goal.subject == sub
                and parsed_goal.object_node == obj
            ):
                return None

    # 3. Hallucination Guard: at least one concept must be grounded in domain concepts
    if domain_concepts is not None and len(domain_concepts) > 0:
        # If neither subject nor object is in known domain concepts, reject
        if sub not in domain_concepts and obj not in domain_concepts:
            return None

    # Parse suggested premise if available
    premise_raw = data.get("suggested_premise")
    premise_tokens = parse_s_expression(premise_raw) if isinstance(premise_raw, str) else None

    reasoning = str(data.get("reasoning", ""))

    return SubgoalResult(
        subgoal=[rel, sub, obj],
        subgoal_str=f"({rel} {sub} {obj})",
        suggested_premise=premise_tokens,
        suggested_premise_str=premise_raw if premise_tokens else None,
        reasoning=reasoning,
        raw_json=data,
    )
