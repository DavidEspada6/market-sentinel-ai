from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.analytics import calculate_risk_metrics
from market_sentinel_ai.domain.operations import SignalRecord
from market_sentinel_ai.domain.paper import PaperTrade
from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal


def _trade(pnl: float, index: int) -> PaperTrade:
    opened = datetime(2026, 9, 19, tzinfo=UTC) + timedelta(minutes=index)
    return PaperTrade(
        symbol="SPY",
        direction=Direction.LONG,
        quantity=10.0,
        entry_price=100.0,
        exit_price=100.0 + pnl / 10.0,
        pnl=pnl,
        opened_at=opened,
        closed_at=opened + timedelta(minutes=5),
    )


class O4RiskMetricsTests(unittest.TestCase):
    def test_metrics_separate_estimated_realized_and_risk_measures(self) -> None:
        signal = Signal(
            prediction=Prediction(
                symbol="SPY",
                horizon_minutes=5,
                direction=Direction.LONG,
                probability=0.8,
                model_name="test",
                generated_at=datetime(2026, 9, 19, tzinfo=UTC),
                expected_return_bps=20.0,
            ),
            confidence=0.8,
            rationale="test",
        )
        record = SignalRecord.from_signal("signal-1", "5m", signal)
        metrics = calculate_risk_metrics(
            [_trade(20.0, 0), _trade(-30.0, 1), _trade(10.0, 2)],
            [record],
            starting_equity=100_000.0,
            max_position_pct=0.02,
        )

        self.assertEqual(metrics.realized_pnl, 0.0)
        self.assertGreater(metrics.estimated_pnl, 0.0)
        self.assertGreater(metrics.var_95, 0.0)
        self.assertGreaterEqual(metrics.cvar_95, metrics.var_95)
        self.assertGreater(metrics.max_drawdown_pct, 0.0)
        self.assertEqual(metrics.sample_size, 3)
        self.assertEqual(metrics.to_dict()["unrealized_pnl"], 0.0)


if __name__ == "__main__":
    unittest.main()
