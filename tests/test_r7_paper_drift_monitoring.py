from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal
from market_sentinel_ai.domain.risk import RiskLimits
from market_sentinel_ai.monitoring import FeatureDriftDetector, JsonlEventLogger
from market_sentinel_ai.paper import PaperTradingLedger
from market_sentinel_ai.ports.features import FeatureRow


class R7Tests(unittest.TestCase):
    def test_paper_ledger_simulates_without_real_orders(self) -> None:
        signal = Signal(
            prediction=Prediction(
                symbol="SPY",
                horizon_minutes=5,
                direction=Direction.LONG,
                probability=0.8,
                model_name="test",
                generated_at=datetime(2026, 9, 19, tzinfo=UTC),
                expected_return_bps=10,
            ),
            confidence=0.8,
            rationale="test",
        )
        ledger = PaperTradingLedger(starting_equity=100_000)

        trade = ledger.simulate_round_trip(
            signal=signal,
            entry_price=100,
            exit_price=101,
            opened_at=datetime(2026, 9, 19, tzinfo=UTC),
            closed_at=datetime(2026, 9, 19, tzinfo=UTC),
            risk=RiskLimits(0.02, 0.03, 1, 2),
        )

        self.assertIsNotNone(trade)
        self.assertGreater(ledger.equity, 100_000)

    def test_feature_drift_detector_flags_shift(self) -> None:
        reference = [
            FeatureRow(symbol="SPY", timestamp_iso=str(index), values={"x": float(index)})
            for index in range(10)
        ]
        current = [
            FeatureRow(symbol="SPY", timestamp_iso=str(index), values={"x": float(index + 100)})
            for index in range(10)
        ]

        report = FeatureDriftDetector(threshold=2.0).compare(reference, current)

        self.assertTrue(report.drifted)
        self.assertGreater(report.scores["x"], 2.0)

    def test_jsonl_event_logger_writes_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            logger = JsonlEventLogger(path)

            logger.log("test", {"ok": True})

            self.assertIn('"event_type": "test"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

