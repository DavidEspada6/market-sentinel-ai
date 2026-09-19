from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import mean, pstdev

from market_sentinel_ai.domain.market import Candle
from market_sentinel_ai.ports.features import FeatureRow


class OHLCVFeatureEngine:
    def __init__(self, rolling_window: int = 20) -> None:
        if rolling_window < 2:
            raise ValueError("rolling_window must be at least 2")
        self.rolling_window = rolling_window

    def transform(self, candles: Sequence[Candle]) -> list[FeatureRow]:
        rows: list[FeatureRow] = []
        returns: list[float] = []
        volumes: list[float] = []

        for index, candle in enumerate(candles):
            previous_close = candles[index - 1].close if index else candle.open
            return_bps = ((candle.close - previous_close) / previous_close) * 10_000
            body_bps = ((candle.close - candle.open) / candle.open) * 10_000
            range_bps = ((candle.high - candle.low) / candle.open) * 10_000
            upper_wick_bps = ((candle.high - max(candle.open, candle.close)) / candle.open) * 10_000
            lower_wick_bps = ((min(candle.open, candle.close) - candle.low) / candle.open) * 10_000

            returns.append(return_bps)
            volumes.append(candle.volume)
            rolling_returns = returns[-self.rolling_window :]
            rolling_volumes = volumes[-self.rolling_window :]
            volume_std = pstdev(rolling_volumes) if len(rolling_volumes) > 1 else 0.0

            rows.append(
                FeatureRow(
                    symbol=candle.symbol,
                    timestamp_iso=candle.opened_at.isoformat(),
                    values={
                        "return_1_bps": return_bps,
                        "body_bps": body_bps,
                        "range_bps": range_bps,
                        "upper_wick_bps": max(0.0, upper_wick_bps),
                        "lower_wick_bps": max(0.0, lower_wick_bps),
                        "rolling_return_mean_bps": mean(rolling_returns),
                        "rolling_volatility_bps": pstdev(rolling_returns)
                        if len(rolling_returns) > 1
                        else 0.0,
                        "volume_zscore": (candle.volume - mean(rolling_volumes)) / volume_std
                        if volume_std
                        else 0.0,
                        "log_volume": math.log1p(candle.volume),
                    },
                )
            )

        return rows

