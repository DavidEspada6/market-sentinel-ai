from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from market_sentinel_ai.domain.market import Candle


@dataclass(frozen=True)
class FeatureRow:
    symbol: str
    timestamp_iso: str
    values: dict[str, float]


class FeatureEngine(Protocol):
    def transform(self, candles: Sequence[Candle]) -> Sequence[FeatureRow]:
        """Convert time-ordered market data into features available at each timestamp."""

