"""Week 11 dataset and learned Tier 1 v2 regression tests."""

import json

import numpy as np
import pytest

from prism.training.dataset import TraceExample, load_trace_jsonl, split_by_run
from prism.training.model import Tier1V2Model, TrainConfig, train_model


def _examples():
    rows = []
    for run in ("run-a", "run-b", "run-c", "run-d"):
        rows.extend([
            TraceExample("(Inheritance A Z)", "(Inheritance A Z)", .9, .9, 1, 4, 0, 1, run, 1, .9),
            TraceExample("(Inheritance X Y)", "(Inheritance A Z)", .9, .4, 2, 4, 3, 0, run, 1, .2),
        ])
    return rows


def test_split_by_run_has_no_leakage():
    train, validation = split_by_run(_examples(), validation_fraction=.25, seed=7)
    assert {x.run_id for x in train}.isdisjoint({x.run_id for x in validation})
    assert {x.outcome for x in train} == {0, 1}


def test_trace_loader_rejects_unfinalized_rows(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({
        "statement": "x", "goal": "g", "on_proof_path": None,
        "domain_name": "r", "step": 1,
    }) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not finalized"):
        load_trace_jsonl([path])


def test_model_trains_round_trips_and_separates_examples(tmp_path):
    examples = _examples()
    model, history = train_model(
        examples, TrainConfig(epochs=50, learning_rate=.01, seed=3), examples,
    )
    assert history.train_loss[-1] < history.train_loss[0]
    assert history.validation_loss
    assert 1 <= history.best_epoch <= history.stopped_epoch
    scores = model.predict_examples(examples)
    assert scores[0] > scores[1]
    checkpoint = model.save(tmp_path / "tier1_v2.npz")
    restored = Tier1V2Model.load(checkpoint)
    np.testing.assert_allclose(scores, restored.predict_examples(examples), atol=1e-10)


def test_missing_v2_checkpoint_uses_safe_search_fallback():
    from prism.core.config import SearchConfig, Tier1Config
    from prism.search.engine import AStarSearchEngine

    facts = [
        ["Sentence", [["Inheritance", "A", "B"], ["stv", .9, .9]], ["1"]],
        ["Sentence", [["Inheritance", "B", "Z"], ["stv", .9, .9]], ["2"]],
    ]
    engine = AStarSearchEngine(
        SearchConfig(max_steps=10),
        Tier1Config(version="v2", model_path="/definitely/missing/model.npz"),
    )
    result = engine.search(facts, facts, ["Inheritance", "A", "Z"])
    assert result.goal_found is True
    assert any(event.startswith("tier1_confidence_fallback") for event in result.fallback_events)
