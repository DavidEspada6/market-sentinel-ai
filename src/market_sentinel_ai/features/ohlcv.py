from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import mean, pstdev

from market_sentinel_ai.domain.market import Candle
from market_sentinel_ai.ports.features import FeatureRow


class OHLCVFeatureEngine:
    def __init__(
        self,
        rolling_window: int = 20,
        *,
        fast_ema_window: int | None = None,
        rsi_window: int = 14,
    ) -> None:
        if rolling_window < 2:
            raise ValueError("rolling_window must be at least 2")
        resolved_fast_window = fast_ema_window or min(5, rolling_window - 1)
        if resolved_fast_window < 2 or resolved_fast_window >= rolling_window:
            raise ValueError("fast_ema_window must be at least 2 and below rolling_window")
        if rsi_window < 2:
            raise ValueError("rsi_window must be at least 2")
        self.rolling_window = rolling_window
        self.fast_ema_window = resolved_fast_window
        self.rsi_window = rsi_window

    def transform(self, candles: Sequence[Candle]) -> list[FeatureRow]:
        rows: list[FeatureRow] = []
        returns: list[float] = []
        volumes: list[float] = []
        true_ranges_bps: list[float] = []
        closes: list[float] = []
        gains: list[float] = []
        losses: list[float] = []
        fast_ema: float | None = None
        slow_ema: float | None = None
        fast_alpha = 2 / (self.fast_ema_window + 1)
        slow_alpha = 2 / (self.rolling_window + 1)

        for index, candle in enumerate(candles):
            previous_close = candles[index - 1].close if index else candle.open
            return_bps = ((candle.close - previous_close) / previous_close) * 10_000
            body_bps = ((candle.close - candle.open) / candle.open) * 10_000
            range_bps = ((candle.high - candle.low) / candle.open) * 10_000
            upper_wick_bps = ((candle.high - max(candle.open, candle.close)) / candle.open) * 10_000
            lower_wick_bps = ((min(candle.open, candle.close) - candle.low) / candle.open) * 10_000
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
            true_range_bps = (true_range / previous_close) * 10_000

            change = candle.close - previous_close
            gains.append(max(0.0, change))
            losses.append(max(0.0, -change))
            gain_window = gains[-self.rsi_window :]
            loss_window = losses[-self.rsi_window :]
            average_gain = mean(gain_window)
            average_loss = mean(loss_window)
            if average_loss:
                rsi = 100 - (100 / (1 + average_gain / average_loss))
            elif average_gain:
                rsi = 100.0
            else:
                rsi = 50.0

            fast_ema = candle.close if fast_ema is None else (
                fast_alpha * candle.close + (1 - fast_alpha) * fast_ema
            )
            slow_ema = candle.close if slow_ema is None else (
                slow_alpha * candle.close + (1 - slow_alpha) * slow_ema
            )

            returns.append(return_bps)
            volumes.append(candle.volume)
            true_ranges_bps.append(true_range_bps)
            closes.append(candle.close)
            rolling_returns = returns[-self.rolling_window :]
            rolling_volumes = volumes[-self.rolling_window :]
            rolling_closes = closes[-self.rolling_window :]
            volume_std = pstdev(rolling_volumes) if len(rolling_volumes) > 1 else 0.0
            reference_3 = closes[max(0, index - 3)]
            reference_5 = closes[max(0, index - 5)]
            minute_of_day = candle.opened_at.hour * 60 + candle.opened_at.minute
            time_angle = (minute_of_day / 1440) * 2 * math.pi
            weekday_angle = (candle.opened_at.weekday() / 7) * 2 * math.pi

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
                        "return_3_bps": ((candle.close - reference_3) / reference_3) * 10_000,
                        "return_5_bps": ((candle.close - reference_5) / reference_5) * 10_000,
                        "atr_bps": mean(true_ranges_bps[-self.rolling_window :]),
                        "rsi": rsi,
                        "ema_fast_distance_bps": ((candle.close - fast_ema) / fast_ema) * 10_000,
                        "ema_slow_distance_bps": ((candle.close - slow_ema) / slow_ema) * 10_000,
                        "ema_cross_bps": ((fast_ema - slow_ema) / slow_ema) * 10_000,
                        "distance_to_high_bps": (
                            (candle.close - max(rolling_closes)) / max(rolling_closes)
                        )
                        * 10_000,
                        "distance_to_low_bps": (
                            (candle.close - min(rolling_closes)) / min(rolling_closes)
                        )
                        * 10_000,
                        "volume_zscore": (candle.volume - mean(rolling_volumes)) / volume_std
                        if volume_std
                        else 0.0,
                        "log_volume": math.log1p(candle.volume),
                        "time_sin": math.sin(time_angle),
                        "time_cos": math.cos(time_angle),
                        "weekday_sin": math.sin(weekday_angle),
                        "weekday_cos": math.cos(weekday_angle),
                    },
                )
            )

        return rows
