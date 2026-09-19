from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.ports.features import FeatureRow
from market_sentinel_ai.ports.models import PredictiveModel


@dataclass(frozen=True)
class WeightedModel:
    model: PredictiveModel
    weight: float


class WeightedEnsembleModel:
    def __init__(
        self,
        models: Sequence[WeightedModel],
        horizon_minutes: int,
        min_confidence: float = 0.52,
    ) -> None:
        if not models:
            raise ValueError("models cannot be empty")
        if any(item.weight <= 0 for item in models):
            raise ValueError("model weights must be positive")
        self.models = tuple(models)
        self.horizon_minutes = horizon_minutes
        self.min_confidence = min_confidence

    @property
    def name(self) -> str:
        return "weighted-ensemble"

    def predict(self, features: Sequence[FeatureRow]) -> Prediction:
        scores = {Direction.LONG: 0.0, Direction.SHORT: 0.0, Direction.NO_TRADE: 0.0}
        total_weight = sum(item.weight for item in self.models)
        model_votes: dict[str, str] = {}

        for item in self.models:
            prediction = item.model.predict(features)
            scores[prediction.direction] += item.weight * prediction.probability
            model_votes[prediction.model_name] = prediction.direction.value

        normalized = {direction: score / total_weight for direction, score in scores.items()}
        direction = max(normalized, key=normalized.get)
        confidence = normalized[direction]
        if confidence < self.min_confidence:
            direction = Direction.NO_TRADE

        return Prediction(
            symbol=features[-1].symbol,
            horizon_minutes=self.horizon_minutes,
            direction=direction,
            probability=confidence,
            model_name=self.name,
            generated_at=datetime.now(tz=UTC),
            metadata=model_votes,
        )

