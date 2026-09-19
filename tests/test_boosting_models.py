from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_sentinel_ai.adapters.market_data import DemoMarketDataProvider
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.features import OHLCVFeatureEngine
from market_sentinel_ai.ml.datasets import build_directional_examples
from market_sentinel_ai.models import (
    LightGBMDirectionalModel,
    ModelArtifactError,
    XGBoostDirectionalModel,
)


class BoostingModelTests(unittest.TestCase):
    def setUp(self) -> None:
        provider = DemoMarketDataProvider()
        start = datetime(2026, 9, 18, tzinfo=UTC)
        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.FIVE_MINUTES,
                start,
                start + timedelta(minutes=5 * 180),
            )
        )
        self.examples = build_directional_examples(
            candles,
            OHLCVFeatureEngine(rolling_window=20),
            horizon_candles=1,
        )
        self.features = OHLCVFeatureEngine(rolling_window=20).transform(candles)

    def test_xgboost_trains_predicts_and_round_trips_native_artifact(self) -> None:
        model = XGBoostDirectionalModel(n_estimators=8, max_depth=2)
        model.fit(self.examples[:120])
        prediction = model.predict(self.features[120:121])

        self.assertEqual(prediction.model_name, "xgboost-directional")
        self.assertGreaterEqual(prediction.probability, 0.5)
        with tempfile.TemporaryDirectory() as directory:
            path = model.save(Path(directory) / "xgb")
            restored = XGBoostDirectionalModel.load(path.parent)
            restored_prediction = restored.predict(self.features[120:121])

        self.assertAlmostEqual(
            prediction.metadata["probability_long"],
            restored_prediction.metadata["probability_long"],
            places=6,
        )

    def test_lightgbm_trains_predicts_and_round_trips_native_artifact(self) -> None:
        model = LightGBMDirectionalModel(n_estimators=8, max_depth=2)
        model.fit(self.examples[:120])
        prediction = model.predict(self.features[120:121])

        self.assertEqual(prediction.model_name, "lightgbm-directional")
        self.assertGreaterEqual(prediction.probability, 0.5)
        with tempfile.TemporaryDirectory() as directory:
            path = model.save(Path(directory) / "lgbm")
            restored = LightGBMDirectionalModel.load(path.parent)
            restored_prediction = restored.predict(self.features[120:121])

        self.assertAlmostEqual(
            prediction.metadata["probability_long"],
            restored_prediction.metadata["probability_long"],
            places=6,
        )

    def test_artifact_checksum_is_verified(self) -> None:
        model = XGBoostDirectionalModel(n_estimators=4, max_depth=2)
        model.fit(self.examples[:120])
        with tempfile.TemporaryDirectory() as directory:
            artifact_dir = Path(directory) / "xgb"
            model.save(artifact_dir)
            (artifact_dir / "model.json").write_text("tampered", encoding="utf-8")

            with self.assertRaises(ModelArtifactError):
                XGBoostDirectionalModel.load(artifact_dir)


if __name__ == "__main__":
    unittest.main()
