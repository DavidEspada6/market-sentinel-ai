from __future__ import annotations

import unittest
from datetime import UTC, datetime

from market_sentinel_ai.alerts import DryRunAlertChannel
from market_sentinel_ai.dashboard import DashboardViewModel, render_dashboard
from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.ports.backtesting import BacktestReport
from market_sentinel_ai.signals import SignalEngine


class SignalAlertDashboardTests(unittest.TestCase):
    def test_signal_engine_keeps_high_confidence_long(self) -> None:
        prediction = Prediction(
            symbol="SPY",
            horizon_minutes=5,
            direction=Direction.LONG,
            probability=0.78,
            model_name="test",
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
            expected_return_bps=8.0,
        )

        signal = SignalEngine(min_probability=0.6, min_expected_return_bps=3).from_prediction(
            prediction
        )

        self.assertEqual(signal.prediction.direction, Direction.LONG)
        self.assertTrue(signal.is_actionable)

    def test_dry_run_alert_channel_records_signal(self) -> None:
        prediction = Prediction(
            symbol="SPY",
            horizon_minutes=5,
            direction=Direction.SHORT,
            probability=0.7,
            model_name="test",
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
            expected_return_bps=-6.0,
        )
        signal = SignalEngine(min_probability=0.6, min_expected_return_bps=3).from_prediction(
            prediction
        )
        channel = DryRunAlertChannel()

        alert_id = channel.send(signal)

        self.assertEqual(alert_id, "dry-run-1")
        self.assertEqual(channel.sent, [signal])

    def test_dashboard_renders_signal_and_metrics(self) -> None:
        prediction = Prediction(
            symbol="SPY",
            horizon_minutes=5,
            direction=Direction.LONG,
            probability=0.78,
            model_name="test",
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
            expected_return_bps=8.0,
        )
        signal = SignalEngine(min_probability=0.6, min_expected_return_bps=3).from_prediction(
            prediction
        )
        html = render_dashboard(
            DashboardViewModel(
                title="Market Sentinel AI",
                generated_at_iso="2026-09-19T00:00:00+00:00",
                signals=(signal,),
                backtest=BacktestReport(
                    trades=10,
                    win_rate=0.6,
                    expectancy_bps=3.2,
                    profit_factor=1.4,
                    sharpe=1.1,
                    sortino=1.2,
                    max_drawdown_pct=4.5,
                ),
                walk_forward={"average_accuracy": 0.55, "average_coverage": 0.8},
            )
        )

        self.assertIn("Market Sentinel AI", html)
        self.assertIn("SPY", html)
        self.assertIn("LONG", html)


if __name__ == "__main__":
    unittest.main()

