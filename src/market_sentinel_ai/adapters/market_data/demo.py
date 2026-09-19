from __future__ import annotations

import math
import random
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.domain.market import Candle, Timeframe


_TIMEFRAME_MINUTES: dict[Timeframe, int] = {
    Timeframe.ONE_MINUTE: 1,
    Timeframe.FIVE_MINUTES: 5,
    Timeframe.FIFTEEN_MINUTES: 15,
    Timeframe.ONE_HOUR: 60,
    Timeframe.ONE_DAY: 1440,
}


class DemoMarketDataProvider:
    """Deterministic synthetic OHLCV data for tests, demos and local development."""

    def historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Iterable[Candle]:
        step = timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
        current = _as_utc(start)
        end_utc = _as_utc(end)
        price = _initial_price(symbol)
        index = 0

        while current < end_utc:
            rng = random.Random(f"{symbol}:{timeframe}:{current.isoformat()}")
            drift = math.sin(index / 11) * 0.08
            shock = rng.uniform(-0.35, 0.35)
            open_price = price
            close_price = max(0.01, open_price * (1 + (drift + shock) / 10_000))
            high = max(open_price, close_price) * (1 + abs(rng.uniform(0.1, 0.9)) / 10_000)
            low = min(open_price, close_price) * (1 - abs(rng.uniform(0.1, 0.9)) / 10_000)
            volume = 100_000 + rng.randint(0, 25_000) + int(abs(shock) * 5_000)

            yield Candle(
                symbol=symbol.upper(),
                timeframe=timeframe,
                opened_at=current,
                open=round(open_price, 6),
                high=round(high, 6),
                low=round(low, 6),
                close=round(close_price, 6),
                volume=float(volume),
            )

            price = close_price
            current += step
            index += 1

    def stream_candles(self, symbol: str, timeframe: Timeframe) -> Iterable[Candle]:
        now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        step = timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
        start = now - step * 100
        while True:
            yield from self.historical_candles(symbol, timeframe, start, start + step)
            start += step


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _initial_price(symbol: str) -> float:
    seed = sum(ord(char) for char in symbol.upper())
    return 50.0 + (seed % 450)

