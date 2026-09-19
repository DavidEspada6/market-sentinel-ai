from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.features import OHLCVFeatureEngine
from market_sentinel_ai.models import AdaptiveDirectionalModel


class AdaptiveModelTests(unittest.TestCase):
    def test_feature_engine_emits_predictive_candle_features(self) -> None:
        candles = self._candles(20)

        row = OHLCVFeatureEngine().transform(candles)[-1]

        self.assertIn("return_12_bps", row.values)
        self.assertIn("bollinger_position", row.values)
        self.assertIn("ema_cross_slope_bps", row.values)
        self.assertIn("close_location", row.values)

    def test_adaptive_model_trains_and_reports_out_of_sample_metrics(self) -> None:
        candles = self._candles(260)
        features = OHLCVFeatureEngine().transform(candles)
        model = AdaptiveDirectionalModel(horizon_minutes=15)

        model.fit(candles, features, round_trip_cost_bps=7.0)
        prediction = model.predict(features)

        self.assertEqual(model.status["status"], "trained")
        self.assertGreaterEqual(model.status["training_samples"], 120)
        self.assertGreaterEqual(model.status["oos_folds"], 1)
        self.assertGreaterEqual(model.status["oos_recall"], 0.0)
        self.assertIn(prediction.direction, {Direction.LONG, Direction.SHORT, Direction.NO_TRADE})
        self.assertEqual(prediction.model_name, "adaptive-logistic")
        self.assertIn("probability_long", prediction.metadata)

    @staticmethod
    def _candles(count: int) -> list[Candle]:
        candles: list[Candle] = []
        for index in range(count):
            close = 100.0 + index * 0.03 + ((index % 7) - 3) * 0.04
            candles.append(
                Candle(
                    symbol="TEST",
                    timeframe=Timeframe.FIVE_MINUTES,
                    opened_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5),
                    open=close - 0.01,
                    high=close + 0.05,
                    low=close - 0.05,
                    close=close,
                    volume=100_000 + index * 10,
                )
            )
        return candles


if __name__ == "__main__":
    unittest.main()
