"""
Prompt Builder Subsystem for PRISM Tier 2.

Formats the current search context (goal, relevant beliefs, recent derivations)
into a structured instruction prompt for the Strategic LLM Reasoner.
"""

from typing import Any, List, Optional
PROMPT_TEMPLATE = """You are a logical reasoning assistant for a probabilistic inference engine (PLN).

CURRENT GOAL:
{goal_statement}

KNOWN FACTS (top-{top_k} by relevance):
{formatted_beliefs}

DERIVATIONS ATTEMPTED SO FAR (last 5):
{recent_derivation_log}

The forward search has stalled. Select a useful lemma that PLN can derive in
EXACTLY ONE binary inference step from TWO facts explicitly listed above.

For example, from `(Inheritance A B)` and `(Inheritance B C)`, PLN can derive
`(Inheritance A C)`. Do not compress a longer chain into one step. Prefer a
one-step conclusion that joins otherwise disconnected parts of the proof.
Do not repeat the current goal or a fact that is already listed.

Return the lemma as `subgoal`. Return one of its two supporting known facts as
`suggested_premise`. In `reasoning`, name both supporting facts.

Respond in this exact JSON format:
{{
  "subgoal": "(LinkType ConceptA ConceptB)",
  "suggested_premise": "(LinkType ConceptX ConceptY)",
  "reasoning": "brief explanation"
}}"""


def format_term(term: Any) -> str:
    """Format an atomic term or expression into a MeTTa string."""
    if isinstance(term, str):
        return term
    if isinstance(term, (list, tuple)):
        # Check if wrapped in Sentence
        if len(term) >= 2 and term[0] == "Sentence":
            inner = term[1]
            if isinstance(inner, (list, tuple)) and len(inner) >= 1:
                return format_term(inner[0])
        from prism.search.rules import parse_sentence

        parsed = parse_sentence(term)
        if parsed:
            return f"({parsed.relation} {parsed.subject} {parsed.object_node})"
        return "(" + " ".join(format_term(x) for x in term) + ")"
    return str(term)


def format_belief(belief: Any) -> str:
    """Format a belief Sentence into a clean readable string with TV info if available."""
    if isinstance(belief, (list, tuple)) and len(belief) >= 2 and belief[0] == "Sentence":
        stmt_part = belief[1]
        if isinstance(stmt_part, (list, tuple)):
            stmt_str = format_term(stmt_part[0])
            if len(stmt_part) >= 2 and isinstance(stmt_part[1], (list, tuple)):
                tv = stmt_part[1]
                if len(tv) >= 3 and tv[0] == "stv":
                    s, c = tv[1], tv[2]
                    return f"{stmt_str} [stv: {s:.2f}, {c:.2f}]"
            return stmt_str
    return format_term(belief)


def build_stall_prompt(
    goal: Any,
    beliefs: List[Any],
    recent_derivations: Optional[List[Any]] = None,
    top_k: int = 10,
    max_history: int = 5,
) -> str:
    """
    Construct the strategic guidance prompt for the LLM reasoner.

    Args:
        goal: The query goal statement.
        beliefs: Known facts/lemmas in the current state.
        recent_derivations: Recent candidates or transitions attempted.
        top_k: Number of most relevant beliefs to include in context.
        max_history: Number of recent derivation attempts to include.

    Returns:
        str: Fully formatted prompt text.
    """
    goal_str = format_term(goal)

    selected_beliefs = beliefs[:top_k]
    if selected_beliefs:
        formatted_beliefs = "\n".join(
            f"  {i+1}. {format_belief(b)}" for i, b in enumerate(selected_beliefs)
        )
    else:
        formatted_beliefs = "  (No relevant beliefs available)"

    history = recent_derivations or []
    selected_history = history[-max_history:]
    if selected_history:
        formatted_history = "\n".join(
            f"  {i+1}. {format_term(d)}" for i, d in enumerate(selected_history)
        )
    else:
        formatted_history = "  (No prior derivations logged)"

    return PROMPT_TEMPLATE.format(
        goal_statement=goal_str,
        top_k=len(selected_beliefs),
        formatted_beliefs=formatted_beliefs,
        recent_derivation_log=formatted_history,
    )
