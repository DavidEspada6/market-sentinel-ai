from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.features.ohlcv import OHLCVFeatureEngine
from market_sentinel_ai.ports.features import FeatureRow

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
                opened_at=datetime.fromtimestamp(
                    bucket * target_minutes * 60,
                    tz=group[0].opened_at.tzinfo,
                ),
                open=group[0].open,
                high=max(candle.high for candle in group),
                low=min(candle.low for candle in group),
                close=group[-1].close,
                volume=sum(candle.volume for candle in group),
            )
        )
    return aggregated


class AlignedMultiTimeframeFeatureEngine:
    """Join higher-timeframe features without exposing an unfinished candle."""

    def __init__(
        self,
        higher_timeframes: Sequence[Timeframe] = (
            Timeframe.FIFTEEN_MINUTES,
            Timeframe.ONE_HOUR,
        ),
        *,
        base_engine: OHLCVFeatureEngine | None = None,
        higher_engine: OHLCVFeatureEngine | None = None,
    ) -> None:
        if not higher_timeframes:
            raise ValueError("higher_timeframes cannot be empty")
        if len(set(higher_timeframes)) != len(higher_timeframes):
            raise ValueError("higher_timeframes must be unique")
        self.higher_timeframes = tuple(higher_timeframes)
        self.base_engine = base_engine or OHLCVFeatureEngine()
        self.higher_engine = higher_engine or OHLCVFeatureEngine()

    def transform(self, candles: Sequence[Candle]) -> list[FeatureRow]:
        if not candles:
            return []
        source_timeframe = candles[0].timeframe
        base_rows = self.base_engine.transform(candles)
        values = [dict(row.values) for row in base_rows]

        for target_timeframe in self.higher_timeframes:
            if _MINUTES[target_timeframe] <= _MINUTES[source_timeframe]:
                raise ValueError("higher timeframes must be greater than the source timeframe")
            aggregated = aggregate_candles(candles, target_timeframe)
            higher_rows = self.higher_engine.transform(aggregated)
            close_times = _aggregation_close_times(candles, target_timeframe)
            for index, candle in enumerate(candles):
                higher_index = bisect_left(close_times, candle.opened_at) - 1
                prefix = f"{target_timeframe.value}_"
                if higher_index < 0:
                    values[index][f"{prefix}available"] = 0.0
                    continue
                values[index][f"{prefix}available"] = 1.0
                values[index].update(
                    {
                        f"{prefix}{name}": feature_value
                        for name, feature_value in higher_rows[higher_index].values.items()
                    }
                )

        return [
            FeatureRow(
                symbol=candle.symbol,
                timestamp_iso=candle.opened_at.isoformat(),
                values=values[index],
            )
            for index, candle in enumerate(candles)
        ]


def _aggregation_close_times(
    candles: Sequence[Candle],
    target_timeframe: Timeframe,
) -> list[datetime]:
    target_minutes = _MINUTES[target_timeframe]
    buckets: dict[int, list[Candle]] = defaultdict(list)
    for candle in candles:
        bucket = int(candle.opened_at.timestamp() // (target_minutes * 60))
        buckets[bucket].append(candle)
    return [
        sorted(buckets[bucket], key=lambda item: item.opened_at)[-1].opened_at
        for bucket in sorted(buckets)
    ]
