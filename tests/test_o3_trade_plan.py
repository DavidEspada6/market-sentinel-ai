from __future__ import annotations

import unittest
from datetime import UTC, datetime

from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal
from market_sentinel_ai.ports.features import FeatureRow
from market_sentinel_ai.signals import build_trade_plan


class O3TradePlanTests(unittest.TestCase):
    def test_actionable_long_plan_has_entry_stop_target_and_expiry(self) -> None:
        signal = Signal(
            prediction=Prediction(
                symbol="SPY",
                horizon_minutes=15,
                direction=Direction.LONG,
                probability=0.8,
                model_name="test",
                generated_at=datetime(2026, 9, 19, tzinfo=UTC),
                expected_return_bps=30.0,
            ),
            confidence=0.8,
            rationale="test",
        )
        plan = build_trade_plan(
            signal,
            Candle(
                "SPY",
                Timeframe.FIVE_MINUTES,
                datetime(2026, 9, 19, tzinfo=UTC),
                100,
                101,
                99,
                100,
                1000,
            ),
            FeatureRow("SPY", "now", {"atr_bps": 10.0}),
            Timeframe.FIVE_MINUTES,
            round_trip_cost_bps=7.0,
        )

        self.assertEqual(plan.action, "ENTER_LONG")
        self.assertLess(plan.stop_loss_price, plan.entry_price)
        self.assertGreater(plan.take_profit_price, plan.entry_price)
        self.assertGreater(plan.reward_risk_ratio, 1.0)
        self.assertIn("plan_valid_until", plan.to_metadata())

    def test_no_trade_plan_does_not_recommend_an_entry(self) -> None:
        signal = Signal(
            prediction=Prediction(
                symbol="SPY",
                horizon_minutes=5,
                direction=Direction.NO_TRADE,
                probability=0.5,
                model_name="test",
                generated_at=datetime(2026, 9, 19, tzinfo=UTC),
            ),
            confidence=0.5,
            rationale="wait",
        )
        plan = build_trade_plan(
            signal,
            Candle(
                "SPY",
                Timeframe.FIVE_MINUTES,
                datetime(2026, 9, 19, tzinfo=UTC),
                100,
                101,
                99,
                100,
                1000,
            ),
            FeatureRow("SPY", "now", {"atr_bps": 10.0}),
            Timeframe.FIVE_MINUTES,
            round_trip_cost_bps=7.0,
        )

        self.assertEqual(plan.action, "WAIT")
        self.assertIsNone(plan.entry_price)
        self.assertIn("Do not open", plan.exit_guidance)


if __name__ == "__main__":
    unittest.main()
