from __future__ import annotations

from collections.abc import Sequence

from market_sentinel_ai.domain.market import Candle


def validate_candle_sequence(candles: Sequence[Candle]) -> None:
    if not candles:
        return

    previous = candles[0]
    for candle in candles[1:]:
        if candle.symbol != previous.symbol:
            raise ValueError("all candles in a sequence must share the same symbol")
        if candle.timeframe != previous.timeframe:
            raise ValueError("all candles in a sequence must share the same timeframe")
        if candle.opened_at <= previous.opened_at:
            raise ValueError("candles must be strictly ordered by opened_at")
        previous = candle

