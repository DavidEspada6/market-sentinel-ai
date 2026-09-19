from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from market_sentinel_ai.domain.market import Candle, Timeframe


_MINUTES: dict[Timeframe, int] = {
    Timeframe.ONE_MINUTE: 1,
    Timeframe.FIVE_MINUTES: 5,
    Timeframe.FIFTEEN_MINUTES: 15,
    Timeframe.ONE_HOUR: 60,
    Timeframe.ONE_DAY: 1440,
}


def aggregate_candles(candles: Sequence[Candle], target_timeframe: Timeframe) -> list[Candle]:
    if not candles:
        return []
    target_minutes = _MINUTES[target_timeframe]
    source_minutes = _MINUTES[candles[0].timeframe]
    if target_minutes < source_minutes:
        raise ValueError("target timeframe must be greater than or equal to source timeframe")
    if target_minutes == source_minutes:
        return list(candles)

    buckets: dict[int, list[Candle]] = defaultdict(list)
    for candle in candles:
        bucket = int(candle.opened_at.timestamp() // (target_minutes * 60))
        buckets[bucket].append(candle)

    aggregated: list[Candle] = []
    for bucket in sorted(buckets):
        group = sorted(buckets[bucket], key=lambda item: item.opened_at)
        aggregated.append(
            Candle(
                symbol=group[0].symbol,
                timeframe=target_timeframe,
                opened_at=datetime.fromtimestamp(bucket * target_minutes * 60, tz=group[0].opened_at.tzinfo),
                open=group[0].open,
                high=max(candle.high for candle in group),
                low=min(candle.low for candle in group),
                close=group[-1].close,
                volume=sum(candle.volume for candle in group),
            )
        )
    return aggregated

