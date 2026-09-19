from __future__ import annotations

from dataclasses import dataclass

from market_sentinel_ai.domain.prediction import Direction, Signal


@dataclass(frozen=True)
class AstraCostPolicy:
    min_confidence: float
    max_requests_per_day: int

    def should_request_context(self, signal: Signal, requests_used_today: int) -> bool:
        if requests_used_today >= self.max_requests_per_day:
            return False
        if signal.prediction.direction is Direction.NO_TRADE:
            return False
        return signal.confidence >= self.min_confidence

