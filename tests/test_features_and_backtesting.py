from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.backtesting import SimpleBacktestEngine
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.features import OHLCVFeatureEngine
from market_sentinel_ai.models import MomentumBaselineModel


def _trend_candles(count: int, step: float) -> list[Candle]:
    start = datetime(2026, 9, 18, tzinfo=UTC)
    price = 100.0
    candles: list[Candle] = []
    for index in range(count):
        opened_at = start + timedelta(minutes=5 * index)
        close = price + step
        candles.append(
            Candle(
                symbol="SPY",
                timeframe=Timeframe.FIVE_MINUTES,
                opened_at=opened_at,
                open=price,
                high=max(price, close) + 0.05,
                low=min(price, close) - 0.05,
                close=close,
                volume=100_000 + index,
            )
        )
        price = close
    return candles


class FeatureAndBacktestTests(unittest.TestCase):
    def test_feature_engine_emits_one_row_per_candle(self) -> None:
        candles = _trend_candles(5, 0.1)
        rows = OHLCVFeatureEngine(rolling_window=3).transform(candles)

        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[-1].symbol, "SPY")
        self.assertIn("rolling_return_mean_bps", rows[-1].values)
        self.assertGreater(rows[-1].values["rolling_return_mean_bps"], 0)

    def test_baseline_goes_long_on_positive_momentum(self) -> None:
        rows = OHLCVFeatureEngine(rolling_window=3).transform(_trend_candles(8, 0.2))
        prediction = MomentumBaselineModel(
            horizon_minutes=5, momentum_threshold_bps=1
        ).predict(rows)

        self.assertEqual(prediction.direction, Direction.LONG)
        self.assertGreater(prediction.probability, 0.5)

    def test_backtester_includes_costs_and_reports_metrics(self) -> None:
        candles = _trend_candles(12, 0.2)
        engine = SimpleBacktestEngine(
            feature_engine=OHLCVFeatureEngine(rolling_window=3),
            model=MomentumBaselineModel(horizon_minutes=5, momentum_threshold_bps=1),
            fee_bps=1,
            slippage_bps=1,
        )

        report = engine.run(candles)

        self.assertGreater(report.trades, 0)
        self.assertEqual(report.win_rate, 1.0)
        self.assertGreater(report.expectancy_bps, 0)
        self.assertEqual(report.max_drawdown_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
