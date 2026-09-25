"""Week 10 deterministic graceful-degradation tests."""

import json

from prism.core.cache import ScoreCache
from prism.core.config import BidirectionalConfig, SearchConfig, Tier2Config
from prism.core.safety import safe_cached_score
from prism.search.engine import AStarSearchEngine
from prism.search.rules import generate_forward_candidates
from prism.search.bidirectional import BidirectionalSearchEngine
from prism.search.state import SearchNode
from prism.tier2.client import MockLLMClient
from prism.tier2.reasoner import Tier2Reasoner


FACT = ["Sentence", [["Inheritance", "A", "B"], ["stv", 0.9, 0.8]], ["1"]]
GOAL = ["Inheritance", "A", "Z"]


class BrokenCache(ScoreCache):
    def get_or_compute(self, *_args, **_kwargs):
        raise RuntimeError("cache failed")


class MalformedCache(ScoreCache):
    def get_or_compute(self, *_args, **_kwargs):
        return float("nan")


def test_scorer_and_cache_failures_use_confidence_fallback():
    for cache in (BrokenCache(), MalformedCache()):
        score, event = safe_cached_score(cache, FACT, GOAL, lambda *_: 1.0)
        assert score == 0.8
        assert event.startswith("tier1_confidence_fallback")


def test_search_records_score_fallback_without_injecting_beliefs():
    result = AStarSearchEngine(
        SearchConfig(max_steps=1, guided=True), cache=BrokenCache()
    ).search([FACT], [FACT], GOAL, candidate_generator=lambda *_: [])
    assert not result.goal_found
    assert result.goal_sentence is None
    assert result.fallback_events


def test_candidate_or_kernel_failure_returns_controlled_empty_result():
    def broken_generator(*_args, **_kwargs):
        raise RuntimeError("PLN exited")

    result = AStarSearchEngine(SearchConfig(max_steps=2)).search(
        [FACT], [FACT], GOAL, candidate_generator=broken_generator
    )
    assert not result.goal_found
    assert result.goal_sentence is None
    assert result.proof_path == []
    assert result.failure_reason.startswith("candidate_generation_failure")


def test_stage0_failure_uses_full_belief_set(monkeypatch):
    second = ["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.8]], ["2"]]
    expected = ["Sentence", [["Inheritance", "A", "C"], ["stv", 0.7, 0.6]], ["1", "2"]]

    monkeypatch.setattr("prism.stage0.filter_beliefs", lambda *_: (_ for _ in ()).throw(RuntimeError("index failed")))
    monkeypatch.setattr("prism.adapters.petta.runtime.apply_pln_pair", lambda *_: expected)
    candidates = generate_forward_candidates([FACT], [second], goal=["Inheritance", "A", "C"], use_stage0=True)
    assert expected in candidates


def test_tier2_provider_and_malformed_output_are_contained():
    for client in (
        MockLLMClient(error_mode=True),
        MockLLMClient(canned_responses=["not json"]),
        MockLLMClient(canned_responses=[json.dumps({"subgoal": "(Invented X Y)"})]),
    ):
        reasoner = Tier2Reasoner(Tier2Config(stall_steps=1), client)
        assert reasoner.propose_subgoal(GOAL, [FACT], domain_concepts={"A", "B", "Z"}) is None
        assert reasoner.last_failure


def test_invalid_bidirectional_seam_falls_back_to_forward_search():
    second = ["Sentence", [["Inheritance", "B", "C"], ["stv", 0.9, 0.8]], ["2"]]
    injected = ["Sentence", [["Inheritance", "A", "C"], ["stv", 1.0, 1.0]], ["1", "2"]]
    node = SearchNode(1, [FACT, second, injected], [FACT, second, injected], 0, 0, 0, 1, action=injected)
    engine = BidirectionalSearchEngine(
        BidirectionalConfig(max_steps=20), SearchConfig(max_steps=20, beam_width=2)
    )
    result = engine._validate_stitch_or_fallback(
        [node], injected, ["Inheritance", "A", "C"], [FACT, second], [FACT, second], 20
    )
    assert result is not None
    assert result.goal_found
    assert result.fallback_events[0].startswith("bidirectional_forward_fallback")
