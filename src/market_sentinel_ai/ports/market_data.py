from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from market_sentinel_ai.domain.market import Candle, Timeframe


class MarketDataProvider(Protocol):
    def historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Iterable[Candle]:
        """Return normalized historical candles for a symbol and timeframe."""

    def stream_candles(self, symbol: str, timeframe: Timeframe) -> Iterable[Candle]:
        """Yield live or live-like candles. R1 will add concrete adapters."""

