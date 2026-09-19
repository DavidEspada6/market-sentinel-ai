from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime

from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.ml.datasets import TrainingExample
from market_sentinel_ai.ports.features import FeatureRow


class LogisticDirectionalModel:
    def __init__(
        self,
        horizon_minutes: int,
        learning_rate: float = 0.05,
        epochs: int = 200,
        l2: float = 0.001,
        long_threshold: float = 0.55,
        short_threshold: float = 0.45,
    ) -> None:
        self.horizon_minutes = horizon_minutes
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.l2 = l2
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.feature_names: tuple[str, ...] = ()
        self.means: dict[str, float] = {}
        self.scales: dict[str, float] = {}
        self.weights: dict[str, float] = {}
        self.bias = 0.0

    @property
    def name(self) -> str:
        return "logistic-directional"

    def fit(self, examples: Sequence[TrainingExample]) -> None:
        if not examples:
            raise ValueError("examples cannot be empty")

        self.feature_names = tuple(sorted(examples[0].features))
        self.means = {
            name: sum(example.features[name] for example in examples) / len(examples)
            for name in self.feature_names
        }
        self.scales = {
            name: _standard_deviation([example.features[name] for example in examples]) or 1.0
            for name in self.feature_names
        }
        self.weights = {name: 0.0 for name in self.feature_names}
        self.bias = 0.0

        for _ in range(self.epochs):
            gradient = {name: 0.0 for name in self.feature_names}
            bias_gradient = 0.0
            for example in examples:
                values = self._normalize(example.features)
                probability = _sigmoid(
                    self.bias + sum(self.weights[name] * values[name] for name in self.feature_names)
                )
                error = probability - example.label
                bias_gradient += error
                for name in self.feature_names:
                    gradient[name] += error * values[name] + self.l2 * self.weights[name]

            scale = 1 / len(examples)
            self.bias -= self.learning_rate * bias_gradient * scale
            for name in self.feature_names:
                self.weights[name] -= self.learning_rate * gradient[name] * scale

    def predict(self, features: Sequence[FeatureRow]) -> Prediction:
        if not self.feature_names:
            raise ValueError("model must be fit before prediction")
        if not features:
            raise ValueError("features cannot be empty")

        latest = features[-1]
        values = self._normalize(latest.values)
        probability_long = _sigmoid(
            self.bias + sum(self.weights[name] * values[name] for name in self.feature_names)
        )
        if probability_long >= self.long_threshold:
            direction = Direction.LONG
            probability = probability_long
        elif probability_long <= self.short_threshold:
            direction = Direction.SHORT
            probability = 1 - probability_long
        else:
            direction = Direction.NO_TRADE
            probability = max(probability_long, 1 - probability_long)

        return Prediction(
            symbol=latest.symbol,
            horizon_minutes=self.horizon_minutes,
            direction=direction,
            probability=probability,
            model_name=self.name,
            generated_at=datetime.now(tz=UTC),
            metadata={"probability_long": probability_long},
        )

    def _normalize(self, values: dict[str, float]) -> dict[str, float]:
        return {
            name: (values[name] - self.means[name]) / self.scales[name]
            for name in self.feature_names
        }


def _sigmoid(value: float) -> float:
    if value < -60:
        return 0.0
    if value > 60:
        return 1.0
    return 1 / (1 + math.exp(-value))


def _standard_deviation(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    average = sum(values) / len(values)
    variance = sum((value - average) ** 2 for value in values) / len(values)
    return math.sqrt(variance)

