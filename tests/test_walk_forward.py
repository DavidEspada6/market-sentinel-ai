from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.adapters.market_data import DemoMarketDataProvider
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.features import OHLCVFeatureEngine
from market_sentinel_ai.ml import WalkForwardEvaluator, WalkForwardSplit, build_directional_examples
from market_sentinel_ai.models import LogisticDirectionalModel


class WalkForwardTests(unittest.TestCase):
    def test_dataset_builder_shifts_labels_forward(self) -> None:
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

        examples = build_directional_examples(candles, OHLCVFeatureEngine(rolling_window=3))

        self.assertEqual(len(examples), len(candles) - 1)
        self.assertEqual(examples[0].timestamp_iso, candles[0].opened_at.isoformat())
        self.assertIn(examples[0].label, {0, 1})

    def test_walk_forward_evaluator_returns_fold_metrics(self) -> None:
        provider = DemoMarketDataProvider()
        start = datetime(2026, 9, 18, tzinfo=UTC)
        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.FIVE_MINUTES,
                start,
                start + timedelta(minutes=5 * 80),
            )
        )
        examples = build_directional_examples(candles, OHLCVFeatureEngine(rolling_window=5))
        evaluator = WalkForwardEvaluator(
            model_factory=lambda: LogisticDirectionalModel(horizon_minutes=5, epochs=25),
            splitter=WalkForwardSplit(train_size=30, test_size=10),
        )

        report = evaluator.evaluate(examples)

        self.assertGreaterEqual(len(report.folds), 3)
        self.assertGreaterEqual(report.average_coverage, 0.0)
        self.assertLessEqual(report.average_accuracy, 1.0)

    def test_purged_split_leaves_gap_before_each_test_window(self) -> None:
        provider = DemoMarketDataProvider()
        start = datetime(2026, 9, 18, tzinfo=UTC)
        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.FIVE_MINUTES,
                start,
                start + timedelta(minutes=5 * 100),
            )
        )
        examples = build_directional_examples(candles, OHLCVFeatureEngine(rolling_window=5))

        folds = WalkForwardSplit(
            train_size=30,
            test_size=10,
            purge_size=2,
        ).split(examples)

        self.assertGreaterEqual(len(folds), 3)
        self.assertTrue(all(fold.test_start - fold.train_end == 2 for fold in folds))


if __name__ == "__main__":
    unittest.main()

