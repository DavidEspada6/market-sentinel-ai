from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from market_sentinel_ai.domain.market import Candle, Timeframe


class CandleRepository(Protocol):
    def upsert_many(self, candles: Iterable[Candle]) -> int:
        """Insert or update candles and return the number of accepted records."""

    def list_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return candles in ascending timestamp order."""

