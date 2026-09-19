from __future__ import annotations

from typing import Protocol, Sequence

from market_sentinel_ai.domain.prediction import Prediction
from market_sentinel_ai.ports.features import FeatureRow


class PredictiveModel(Protocol):
    @property
    def name(self) -> str:
        """Stable model name used in reports and signals."""

    def predict(self, features: Sequence[FeatureRow]) -> Prediction:
        """Predict a market direction from features."""

