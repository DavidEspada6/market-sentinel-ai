from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.ports.features import FeatureRow
from market_sentinel_ai.ports.models import PredictiveModel
from market_sentinel_ai.regime import Regime, VolatilityRegimeDetector


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


class RegimeAwareEnsembleModel:
    def __init__(
        self,
        models_by_regime: dict[Regime, Sequence[WeightedModel]],
        horizon_minutes: int,
        *,
        detector: VolatilityRegimeDetector | None = None,
        min_confidence: float = 0.52,
    ) -> None:
        if not models_by_regime:
            raise ValueError("models_by_regime cannot be empty")
        self.models_by_regime = {
            regime: tuple(models) for regime, models in models_by_regime.items()
        }
        if any(not models for models in self.models_by_regime.values()):
            raise ValueError("every regime must have at least one model")
        self.horizon_minutes = horizon_minutes
        self.detector = detector or VolatilityRegimeDetector()
        self.min_confidence = min_confidence

    @property
    def name(self) -> str:
        return "regime-aware-ensemble"

    def predict(self, features: Sequence[FeatureRow]) -> Prediction:
        if not features:
            raise ValueError("features cannot be empty")
        regime = self.detector.detect(list(features))
        selected = self.models_by_regime.get(regime)
        if selected is None:
            selected = next(iter(self.models_by_regime.values()))
        prediction = WeightedEnsembleModel(
            selected,
            horizon_minutes=self.horizon_minutes,
            min_confidence=self.min_confidence,
        ).predict(features)
        return Prediction(
            symbol=prediction.symbol,
            horizon_minutes=prediction.horizon_minutes,
            direction=prediction.direction,
            probability=prediction.probability,
            model_name=self.name,
            generated_at=prediction.generated_at,
            expected_return_bps=prediction.expected_return_bps,
            metadata={**prediction.metadata, "regime": regime.value},
        )
