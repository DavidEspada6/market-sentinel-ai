from __future__ import annotations

import unittest
from datetime import UTC, datetime

from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal
from market_sentinel_ai.reasoning.policy import AstraCostPolicy


def _signal(direction: Direction, confidence: float) -> Signal:
    return Signal(
        prediction=Prediction(
            symbol="SPY",
            horizon_minutes=15,
            direction=direction,
            probability=confidence,
            model_name="test-model",
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
        ),
        confidence=confidence,
        rationale="test",
    )


class AstraCostPolicyTests(unittest.TestCase):
    def test_blocks_no_trade_signals(self) -> None:
        policy = AstraCostPolicy(min_confidence=0.7, max_requests_per_day=5)

        self.assertFalse(policy.should_request_context(_signal(Direction.NO_TRADE, 0.95), 0))

    def test_allows_high_confidence_actionable_signal(self) -> None:
        policy = AstraCostPolicy(min_confidence=0.7, max_requests_per_day=5)

        self.assertTrue(policy.should_request_context(_signal(Direction.LONG, 0.82), 0))

    def test_blocks_when_daily_budget_is_used(self) -> None:
        policy = AstraCostPolicy(min_confidence=0.7, max_requests_per_day=5)

        self.assertFalse(policy.should_request_context(_signal(Direction.SHORT, 0.82), 5))


if __name__ == "__main__":
    unittest.main()

