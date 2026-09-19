from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from math import tanh

from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.ports.features import FeatureRow


class MomentumBaselineModel:
    def __init__(
        self,
        horizon_minutes: int,
        momentum_threshold_bps: float = 1.0,
        max_volatility_bps: float = 50.0,
    ) -> None:
        self.horizon_minutes = horizon_minutes
        self.momentum_threshold_bps = momentum_threshold_bps
        self.max_volatility_bps = max_volatility_bps

    @property
    def name(self) -> str:
        return "momentum-baseline"

    def predict(self, features: Sequence[FeatureRow]) -> Prediction:
        if not features:
            raise ValueError("features cannot be empty")

        latest = features[-1]
        momentum = latest.values["rolling_return_mean_bps"]
        volatility = latest.values["rolling_volatility_bps"]
        score = abs(momentum) / max(self.momentum_threshold_bps, 1e-9)
        probability = min(0.95, 0.5 + 0.45 * tanh(score / 3))

        if volatility > self.max_volatility_bps or abs(momentum) < self.momentum_threshold_bps:
            direction = Direction.NO_TRADE
            probability = min(probability, 0.55)
        elif momentum > 0:
            direction = Direction.LONG
        else:
            direction = Direction.SHORT

        return Prediction(
            symbol=latest.symbol,
            horizon_minutes=self.horizon_minutes,
            direction=direction,
            probability=probability,
            model_name=self.name,
            generated_at=datetime.now(tz=UTC),
            expected_return_bps=momentum,
            metadata={
                "momentum_bps": momentum,
                "volatility_bps": volatility,
            },
        )

