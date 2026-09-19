from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.adapters.market_data import DemoMarketDataProvider, DemoOrderBookProvider
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.features import (
    OHLCVFeatureEngine,
    OrderFlowFeatureEngine,
    aggregate_candles,
)
from market_sentinel_ai.models import WeightedEnsembleModel, WeightedModel
from market_sentinel_ai.ports.features import FeatureRow
from market_sentinel_ai.regime import Regime, VolatilityRegimeDetector


class FixedModel:
    def __init__(self, direction: Direction, probability: float) -> None:
        self.direction = direction
        self.probability = probability

    @property
    def name(self) -> str:
        return f"fixed-{self.direction.value}"

    def predict(self, features: list[FeatureRow]) -> Prediction:
        return Prediction(
            symbol=features[-1].symbol,
            horizon_minutes=5,
            direction=self.direction,
            probability=self.probability,
            model_name=self.name,
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
        )


class R5Tests(unittest.TestCase):
    def test_order_flow_features_include_spread_and_imbalance(self) -> None:
        provider = DemoMarketDataProvider()
        start = datetime(2026, 9, 18, tzinfo=UTC)
        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.FIVE_MINUTES,
                start,
                start + timedelta(minutes=10),
            )
        )
        snapshots = list(DemoOrderBookProvider().snapshots_from_candles(candles))
        rows = OrderFlowFeatureEngine().transform(snapshots)

        self.assertEqual(len(rows), 2)
        self.assertGreater(rows[-1].values["book_spread_bps"], 0)
        self.assertGreaterEqual(rows[-1].values["book_imbalance"], -1)
        self.assertLessEqual(rows[-1].values["book_imbalance"], 1)

    def test_aggregate_candles_to_higher_timeframe(self) -> None:
        provider = DemoMarketDataProvider()
        start = datetime(2026, 9, 18, tzinfo=UTC)
        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.FIVE_MINUTES,
                start,
                start + timedelta(minutes=30),
            )
        )

        aggregated = aggregate_candles(candles, Timeframe.FIFTEEN_MINUTES)

        self.assertEqual(len(aggregated), 2)
        self.assertEqual(aggregated[0].volume, sum(candle.volume for candle in candles[:3]))

    def test_weighted_ensemble_combines_directional_votes(self) -> None:
        features = [
            FeatureRow(symbol="SPY", timestamp_iso="2026-09-19T00:00:00+00:00", values={})
        ]
        ensemble = WeightedEnsembleModel(
            models=(
                WeightedModel(FixedModel(Direction.LONG, 0.8), 0.7),
                WeightedModel(FixedModel(Direction.SHORT, 0.6), 0.3),
            ),
            horizon_minutes=5,
            min_confidence=0.5,
        )

        prediction = ensemble.predict(features)

        self.assertEqual(prediction.direction, Direction.LONG)

    def test_volatility_regime_detector_uses_latest_feature_row(self) -> None:
        provider = DemoMarketDataProvider()
        start = datetime(2026, 9, 18, tzinfo=UTC)
        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.FIVE_MINUTES,
                start,
                start + timedelta(minutes=40),
            )
        )
        features = OHLCVFeatureEngine(rolling_window=5).transform(candles)

        regime = VolatilityRegimeDetector(low_threshold_bps=0.0, high_threshold_bps=10_000).detect(
            features
        )

        self.assertEqual(regime, Regime.NORMAL)


if __name__ == "__main__":
    unittest.main()

