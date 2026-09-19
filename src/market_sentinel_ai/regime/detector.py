from __future__ import annotations

from enum import StrEnum

from market_sentinel_ai.ports.features import FeatureRow


class Regime(StrEnum):
    LOW_VOLATILITY = "LOW_VOLATILITY"
    NORMAL = "NORMAL"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


class VolatilityRegimeDetector:
    def __init__(self, low_threshold_bps: float = 3.0, high_threshold_bps: float = 15.0) -> None:
        self.low_threshold_bps = low_threshold_bps
        self.high_threshold_bps = high_threshold_bps

    def detect(self, features: list[FeatureRow]) -> Regime:
        if not features:
            return Regime.NORMAL
        volatility = features[-1].values.get("rolling_volatility_bps", 0.0)
        if volatility < self.low_threshold_bps:
            return Regime.LOW_VOLATILITY
        if volatility > self.high_threshold_bps:
            return Regime.HIGH_VOLATILITY
        return Regime.NORMAL

