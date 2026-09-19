from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.adapters.market_data import BinanceOrderBookProvider
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.features import AlignedMultiTimeframeFeatureEngine
from market_sentinel_ai.models import RegimeAwareEnsembleModel, WeightedModel
from market_sentinel_ai.ports.features import FeatureRow
from market_sentinel_ai.regime import Regime, VolatilityRegimeDetector


class FixedModel:
    def __init__(self, direction: Direction) -> None:
        self.direction = direction

    @property
    def name(self) -> str:
        return f"fixed-{self.direction.value}"

    def predict(self, features: list[FeatureRow]) -> Prediction:
        return Prediction(
            symbol=features[-1].symbol,
            horizon_minutes=5,
            direction=self.direction,
            probability=0.9,
            model_name=self.name,
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
        )


def _candles(count: int = 12) -> list[Candle]:
    start = datetime(2026, 9, 19, tzinfo=UTC)
    return [
        Candle(
            symbol="SPY",
            timeframe=Timeframe.FIVE_MINUTES,
            opened_at=start + timedelta(minutes=index * 5),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1000.0,
        )
        for index in range(count)
    ]


class C4Tests(unittest.TestCase):
    def test_binance_order_book_adapter_normalizes_public_payload(self) -> None:
        payload = json.dumps(
            {
                "lastUpdateId": 10,
                "bids": [["100.0", "2.0"], ["99.9", "3.0"]],
                "asks": [["100.1", "1.0"], ["100.2", "2.0"]],
            }
        ).encode()
        requested_urls: list[str] = []
        provider = BinanceOrderBookProvider(
            depth=2,
            transport=lambda url: requested_urls.append(url) or payload,
        )

        snapshot = provider.snapshot("btcusdt")

        self.assertEqual(snapshot.symbol, "BTCUSDT")
        self.assertEqual(len(snapshot.bids), 2)
        self.assertGreater(snapshot.imbalance, 0)
        self.assertIn("symbol=BTCUSDT", requested_urls[0])

    def test_aligned_multitimeframe_features_wait_for_higher_close(self) -> None:
        rows = AlignedMultiTimeframeFeatureEngine(
            higher_timeframes=(Timeframe.FIFTEEN_MINUTES,)
        ).transform(_candles())

        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0].values["15m_available"], 0.0)
        self.assertEqual(rows[3].values["15m_available"], 1.0)
        self.assertNotIn("15m_return_1_bps", rows[2].values)
        self.assertIn("15m_return_1_bps", rows[3].values)

    def test_regime_aware_ensemble_selects_high_volatility_models(self) -> None:
        model = RegimeAwareEnsembleModel(
            {
                Regime.NORMAL: (WeightedModel(FixedModel(Direction.LONG), 1.0),),
                Regime.HIGH_VOLATILITY: (
                    WeightedModel(FixedModel(Direction.SHORT), 1.0),
                ),
            },
            horizon_minutes=5,
            detector=VolatilityRegimeDetector(high_threshold_bps=10.0),
        )

        prediction = model.predict(
            [
                FeatureRow(
                    symbol="SPY",
                    timestamp_iso="2026-09-19T00:00:00+00:00",
                    values={"rolling_volatility_bps": 100.0},
                )
            ]
        )

        self.assertEqual(prediction.direction, Direction.SHORT)
        self.assertEqual(prediction.metadata["regime"], Regime.HIGH_VOLATILITY.value)


if __name__ == "__main__":
    unittest.main()
