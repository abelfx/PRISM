"""
Unit tests for PRISM Tier 2 Prompt Builder and Subgoal Parser.
Verifies GATE-7.2 (Schema Parsing & Hallucination Guard) and GATE-7.3 (Exception Safety).
"""

from prism.tier2.parser import parse_subgoal_response
from prism.tier2.prompt import build_stall_prompt


def test_build_stall_prompt_structure():
    """Verify prompt builder formats goal, beliefs, and derivation context."""
    goal = ["Inheritance", "A", "Z"]
    beliefs = [
        ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.9]], ["1"]],
        ["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.9]], ["2"]],
    ]
    recent = [["Inheritance", "A", "B"]]

    prompt = build_stall_prompt(goal, beliefs, recent_derivations=recent)

    assert "CURRENT GOAL:" in prompt
    assert "(Inheritance A Z)" in prompt
    assert "(Inheritance A B)" in prompt
    assert "(Inheritance B C)" in prompt
    assert "DERIVATIONS ATTEMPTED SO FAR" in prompt
    assert "EXACTLY ONE binary inference step" in prompt
    assert "name both supporting facts" in prompt


def test_parse_subgoal_valid_json():
    """Verify clean parsing of valid JSON output into SubgoalResult."""
    payload = """
    {
        "subgoal": "(Inheritance C M)",
        "suggested_premise": "(Inheritance B C)",
        "reasoning": "Bridge concept C to target cluster M."
    }
    """
    domain_concepts = {"A", "B", "C", "M", "Z"}
    res = parse_subgoal_response(payload, domain_concepts=domain_concepts, active_goal=["Inheritance", "A", "Z"])

    assert res is not None
    assert res.subgoal == ["Inheritance", "C", "M"]
    assert res.subgoal_str == "(Inheritance C M)"
    assert res.suggested_premise == ["Inheritance", "B", "C"]
    assert "Bridge" in res.reasoning


def test_parse_subgoal_markdown_code_fence():
    """Verify parser extracts JSON from markdown ```json ... ``` blocks."""
    payload = """
    Here is the strategic subgoal to resolve the reasoning stall:
    ```json
    {
        "subgoal": "(Similarity M Z)",
        "suggested_premise": "(Inheritance A M)",
        "reasoning": "M is transitively similar to Z."
    }
    ```
    Good luck!
    """
    domain_concepts = {"A", "M", "Z"}
    res = parse_subgoal_response(payload, domain_concepts=domain_concepts)

    assert res is not None
    assert res.subgoal == ["Similarity", "M", "Z"]


def test_parse_subgoal_invalid_relation_rejection():
    """Verify non-PLN relations are rejected by relation guard."""
    payload = """{"subgoal": "(RandomFooLink A M)", "reasoning": "invalid link"}"""
    res = parse_subgoal_response(payload, domain_concepts={"A", "M"})
    assert res is None


def test_parse_subgoal_hallucination_guard():
    """Verify GATE-7.2: Rejects subgoals proposing completely ungrounded concepts."""
    payload = """{"subgoal": "(Inheritance AlienConcept FooEntity)", "reasoning": "hallucination"}"""
    domain_concepts = {"A", "B", "C", "Z"}
    res = parse_subgoal_response(payload, domain_concepts=domain_concepts)
    assert res is None


def test_parse_subgoal_trivial_self_goal_rejection():
    """Verify rejection of trivial restatement of the active query goal."""
    payload = """{"subgoal": "(Inheritance A Z)", "reasoning": "trivial goal copy"}"""
    domain_concepts = {"A", "Z"}
    active_goal = ["Inheritance", "A", "Z"]
    res = parse_subgoal_response(payload, domain_concepts=domain_concepts, active_goal=active_goal)
    assert res is None


def test_parse_subgoal_malformed_json_fallback():
    """Verify GATE-7.3: Malformed text returns None gracefully without throwing exceptions."""
    res = parse_subgoal_response("This is not valid json at all {broken: True", domain_concepts={"A"})
    assert res is None

    res_empty = parse_subgoal_response("", domain_concepts={"A"})
    assert res_empty is None
