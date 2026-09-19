"""
Unit tests for PRISM Tier 2 LLM Client and Reasoner.
Verifies client instantiation, OpenRouter configuration, and reasoner fallback.
"""

import json
import pytest
from prism.core.config import Tier2Config
from prism.tier2.client import MockLLMClient, OpenRouterClient, create_llm_client
from prism.tier2.reasoner import Tier2Reasoner


def test_mock_llm_client_canned_response():
    """Verify mock client returns pre-configured canned responses."""
    canned = json.dumps({"subgoal": "(Inheritance B M)", "reasoning": "test"})
    client = MockLLMClient(canned_responses=[canned])

    out = client.generate("test prompt")
    assert out == canned
    assert len(client.call_history) == 1


def test_mock_llm_client_dynamic_synthesis():
    """Verify mock client synthesizes valid bridging JSON from prompt context."""
    client = MockLLMClient()
    prompt = """
    CURRENT GOAL:
    (Inheritance A Z)

    KNOWN FACTS:
    (Inheritance A B)
    (Inheritance B C)
    """
    out = client.generate(prompt)
    data = json.loads(out)
    assert "subgoal" in data
    assert "(Inheritance" in data["subgoal"]


def test_mock_llm_client_error_simulation():
    """Verify simulated error mode raises RuntimeError."""
    client = MockLLMClient(error_mode=True)
    with pytest.raises(RuntimeError):
        client.generate("hello")


def test_openrouter_client_missing_key():
    """Verify OpenRouterClient raises clean error if no API key is provided."""
    cfg = Tier2Config(backend="openrouter", api_key="")
    # Ensure env var is not overriding during test
    client = OpenRouterClient(cfg)
    client.api_key = ""  # Force empty
    with pytest.raises(RuntimeError, match="OpenRouter API key not configured"):
        client.generate("test")


def test_create_llm_client_factory(monkeypatch):
    """Verify create_llm_client factory falls back safely."""
    cfg_mock = Tier2Config(backend="mock")
    c_mock = create_llm_client(cfg_mock)
    assert isinstance(c_mock, MockLLMClient)

    # Missing openrouter key falls back to mock
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    cfg_or = Tier2Config(backend="openrouter", api_key="")
    c_or = create_llm_client(cfg_or)
    assert isinstance(c_or, MockLLMClient)


def test_tier2_reasoner_propose_subgoal_success():
    """Verify end-to-end propose_subgoal produces validated SubgoalResult."""
    cfg = Tier2Config(stall_threshold=0.20, stall_steps=2)
    canned = json.dumps({
        "subgoal": "(Inheritance C M)",
        "suggested_premise": "(Inheritance B C)",
        "reasoning": "Bridge C to M"
    })
    client = MockLLMClient(canned_responses=[canned])
    reasoner = Tier2Reasoner(config=cfg, client=client)

    goal = ["Inheritance", "A", "Z"]
    beliefs = [["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.9]], ["1"]]]
    domain_concepts = {"A", "B", "C", "M", "Z"}

    res = reasoner.propose_subgoal(
        goal=goal,
        beliefs=beliefs,
        domain_concepts=domain_concepts,
    )

    assert res is not None
    assert res.subgoal == ["Inheritance", "C", "M"]
    assert reasoner.successful_subgoals == 1


def test_tier2_reasoner_error_containment():
    """Verify GATE-7.3: Exception during generation returns None and does not crash."""
    cfg = Tier2Config()
    client = MockLLMClient(error_mode=True)
    reasoner = Tier2Reasoner(config=cfg, client=client)

    goal = ["Inheritance", "A", "Z"]
    beliefs = []

    res = reasoner.propose_subgoal(goal, beliefs)
    assert res is None  # Graceful fallback
