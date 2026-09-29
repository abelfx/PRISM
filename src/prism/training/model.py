"""NumPy implementation of the Week 11 learned-embedding Tier 1 MLP."""

from __future__ import annotations

from dataclasses import dataclass
import copy
import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from prism.training.dataset import TraceExample
from prism.tier1.heuristic_v1 import extract_atoms


@dataclass(frozen=True)
class TrainConfig:
    embedding_dim: int = 16
    hidden_1: int = 128
    hidden_2: int = 64
    epochs: int = 100
    learning_rate: float = 0.003
    weight_decay: float = 1e-5
    seed: int = 42
    early_stopping_patience: int = 20


@dataclass
class TrainingHistory:
    """Per-epoch optimization and generalization measurements."""

    objective_loss: List[float]
    train_loss: List[float]
    validation_loss: List[float]
    train_accuracy: List[float]
    validation_accuracy: List[float]
    best_epoch: int
    stopped_epoch: int


class Tier1V2Model:
    """Learned token embeddings followed by Dense(128)-Dense(64)-sigmoid."""

    def __init__(self, vocabulary: Sequence[str], config: TrainConfig = TrainConfig()) -> None:
        self.config = config
        self.vocabulary = ["<UNK>", *sorted(set(vocabulary) - {"<UNK>"})]
        self.token_to_id = {token: idx for idx, token in enumerate(self.vocabulary)}
        rng = np.random.default_rng(config.seed)
        scale = 0.08
        input_dim = (2 * config.embedding_dim) + 4
        self.params: Dict[str, np.ndarray] = {
            "embedding": rng.normal(0.0, scale, (len(self.vocabulary), config.embedding_dim)),
            "w1": rng.normal(0.0, np.sqrt(2 / input_dim), (input_dim, config.hidden_1)),
            "b1": np.zeros(config.hidden_1),
            "w2": rng.normal(0.0, np.sqrt(2 / config.hidden_1), (config.hidden_1, config.hidden_2)),
            "b2": np.zeros(config.hidden_2),
            "w3": rng.normal(0.0, np.sqrt(2 / config.hidden_2), (config.hidden_2, 1)),
            "b3": np.zeros(1),
        }

    def _ids(self, tokens: Sequence[str]) -> np.ndarray:
        values = [self.token_to_id.get(token, 0) for token in tokens]
        return np.asarray(values or [0], dtype=np.int64)

    def _vectorize(self, examples: Sequence[TraceExample]) -> Tuple[np.ndarray, List[np.ndarray], List[np.ndarray]]:
        rows: List[np.ndarray] = []
        candidate_ids: List[np.ndarray] = []
        goal_ids: List[np.ndarray] = []
        embeddings = self.params["embedding"]
        for item in examples:
            cids = self._ids(item.candidate_tokens)
            gids = self._ids(item.goal_tokens)
            candidate_ids.append(cids)
            goal_ids.append(gids)
            rows.append(np.concatenate((embeddings[cids].mean(axis=0), embeddings[gids].mean(axis=0), item.numeric_features)))
        return np.vstack(rows), candidate_ids, goal_ids

    def _forward(self, x: np.ndarray) -> Tuple[np.ndarray, Tuple[np.ndarray, ...]]:
        z1 = x @ self.params["w1"] + self.params["b1"]
        a1 = np.maximum(z1, 0.0)
        z2 = a1 @ self.params["w2"] + self.params["b2"]
        a2 = np.maximum(z2, 0.0)
        logits = (a2 @ self.params["w3"] + self.params["b3"]).reshape(-1)
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
        return probabilities, (x, z1, a1, z2, a2)

    def predict_examples(self, examples: Sequence[TraceExample]) -> np.ndarray:
        if not examples:
            return np.asarray([], dtype=float)
        x, _, _ = self._vectorize(examples)
        return self._forward(x)[0]

    def score(
        self,
        candidate: str,
        goal: str,
        strength: float,
        confidence: float,
        depth: int,
        queue_position: int = 0,
        candidate_pool_size: int = 1,
    ) -> float:
        example = TraceExample(
            candidate=str(candidate), goal=str(goal), strength=strength,
            confidence=confidence, depth=depth, candidate_pool_size=max(1, candidate_pool_size),
            queue_position=max(0, queue_position), outcome=0, run_id="inference", step=0,
            heuristic_score=0.0,
        )
        return float(self.predict_examples([example])[0])

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        metadata = json.dumps({"vocabulary": self.vocabulary, "config": self.config.__dict__})
        np.savez_compressed(target, metadata=np.asarray(metadata), **self.params)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "Tier1V2Model":
        with np.load(Path(path), allow_pickle=False) as checkpoint:
            metadata = json.loads(str(checkpoint["metadata"]))
            model = cls(metadata["vocabulary"], TrainConfig(**metadata["config"]))
            for name in model.params:
                model.params[name] = checkpoint[name].copy()
        return model


def train_model(
    examples: Sequence[TraceExample],
    config: TrainConfig = TrainConfig(),
    validation_examples: Sequence[TraceExample] = (),
) -> Tuple[Tier1V2Model, TrainingHistory]:
    """Train with full-batch binary cross entropy and Adam."""
    if not examples or {item.outcome for item in examples} != {0, 1}:
        raise ValueError("training requires both positive and negative examples")
    vocabulary = {token for item in examples for token in (*item.candidate_tokens, *item.goal_tokens)}
    model = Tier1V2Model(sorted(vocabulary), config)
    moments = {name: np.zeros_like(value) for name, value in model.params.items()}
    variances = {name: np.zeros_like(value) for name, value in model.params.items()}
    labels = np.asarray([item.outcome for item in examples], dtype=float)
    positive_weight = len(labels) / max(1.0, 2.0 * labels.sum())
    negative_weight = len(labels) / max(1.0, 2.0 * (len(labels) - labels.sum()))
    sample_weights = np.where(labels == 1.0, positive_weight, negative_weight)
    objective_losses: List[float] = []
    train_losses: List[float] = []
    validation_losses: List[float] = []
    train_accuracies: List[float] = []
    validation_accuracies: List[float] = []
    best_validation_loss = float("inf")
    best_epoch = 0
    best_params = copy.deepcopy(model.params)
    epochs_without_improvement = 0

    def metrics(items: Sequence[TraceExample]) -> Tuple[float, float]:
        if not items:
            return float("nan"), float("nan")
        targets = np.asarray([item.outcome for item in items], dtype=float)
        predictions = np.clip(model.predict_examples(items), 1e-7, 1.0 - 1e-7)
        log_loss = -np.mean(targets * np.log(predictions) + (1.0 - targets) * np.log(1.0 - predictions))
        accuracy = np.mean((predictions >= 0.5) == (targets == 1.0))
        return float(log_loss), float(accuracy)

    for epoch in range(1, config.epochs + 1):
        x, candidate_ids, goal_ids = model._vectorize(examples)
        probabilities, (x, z1, a1, z2, a2) = model._forward(x)
        clipped = np.clip(probabilities, 1e-7, 1.0 - 1e-7)
        loss = -np.mean(sample_weights * (labels * np.log(clipped) + (1.0 - labels) * np.log(1.0 - clipped)))
        objective_losses.append(float(loss))

        dlogits = sample_weights * (probabilities - labels) / len(labels)
        gradients: Dict[str, np.ndarray] = {}
        gradients["w3"] = a2.T @ dlogits[:, None] + config.weight_decay * model.params["w3"]
        gradients["b3"] = np.asarray([dlogits.sum()])
        da2 = dlogits[:, None] @ model.params["w3"].T
        dz2 = da2 * (z2 > 0.0)
        gradients["w2"] = a1.T @ dz2 + config.weight_decay * model.params["w2"]
        gradients["b2"] = dz2.sum(axis=0)
        da1 = dz2 @ model.params["w2"].T
        dz1 = da1 * (z1 > 0.0)
        gradients["w1"] = x.T @ dz1 + config.weight_decay * model.params["w1"]
        gradients["b1"] = dz1.sum(axis=0)
        dx = dz1 @ model.params["w1"].T
        embedding_grad = np.zeros_like(model.params["embedding"])
        dim = config.embedding_dim
        for row, (cids, gids) in enumerate(zip(candidate_ids, goal_ids)):
            np.add.at(embedding_grad, cids, dx[row, :dim] / len(cids))
            np.add.at(embedding_grad, gids, dx[row, dim:2 * dim] / len(gids))
        gradients["embedding"] = embedding_grad

        for name, parameter in model.params.items():
            gradient = np.clip(gradients[name], -5.0, 5.0)
            moments[name] = 0.9 * moments[name] + 0.1 * gradient
            variances[name] = 0.999 * variances[name] + 0.001 * gradient * gradient
            m_hat = moments[name] / (1.0 - 0.9 ** epoch)
            v_hat = variances[name] / (1.0 - 0.999 ** epoch)
            parameter -= config.learning_rate * m_hat / (np.sqrt(v_hat) + 1e-8)

        train_loss, train_accuracy = metrics(examples)
        train_losses.append(train_loss)
        train_accuracies.append(train_accuracy)
        if validation_examples:
            validation_loss, validation_accuracy = metrics(validation_examples)
            validation_losses.append(validation_loss)
            validation_accuracies.append(validation_accuracy)
            if validation_loss < best_validation_loss - 1e-8:
                best_validation_loss = validation_loss
                best_epoch = epoch
                best_params = copy.deepcopy(model.params)
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1
                if epochs_without_improvement >= config.early_stopping_patience:
                    break
        else:
            best_epoch = epoch
            best_params = copy.deepcopy(model.params)

    model.params = best_params
    history = TrainingHistory(
        objective_loss=objective_losses,
        train_loss=train_losses,
        validation_loss=validation_losses,
        train_accuracy=train_accuracies,
        validation_accuracy=validation_accuracies,
        best_epoch=best_epoch,
        stopped_epoch=len(train_losses),
    )
    return model, history
