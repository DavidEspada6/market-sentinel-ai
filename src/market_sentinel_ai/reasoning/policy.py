from __future__ import annotations

import json
from dataclasses import dataclass

from market_sentinel_ai.domain.prediction import Direction, Signal


@dataclass(frozen=True)
class AstraCostPolicy:
    min_confidence: float
    max_requests_per_day: int
    max_input_tokens_per_request: int = 4_000
    max_output_tokens_per_request: int = 800
    max_daily_cost_usd: float = 2.0
    input_cost_per_million: float = 10.0
    output_cost_per_million: float = 50.0

    def should_request_context(
        self,
        signal: Signal,
        requests_used_today: int,
        estimated_cost_used_today: float = 0.0,
        context: dict[str, object] | None = None,
    ) -> bool:
        if requests_used_today >= self.max_requests_per_day:
            return False
        if signal.prediction.direction is Direction.NO_TRADE:
            return False
        if signal.confidence < self.min_confidence:
            return False
        if context is not None:
            input_tokens, _ = self.estimate_tokens(context)
            if input_tokens > self.max_input_tokens_per_request:
                return False
            if (
                estimated_cost_used_today + self.estimated_cost(context)
                > self.max_daily_cost_usd
            ):
                return False
        return True

    def estimate_tokens(self, context: dict[str, object]) -> tuple[int, int]:
        serialized = json.dumps(context, sort_keys=True, default=str)
        input_tokens = max(1, (len(serialized.encode("utf-8")) + 3) // 4)
        return input_tokens, self.max_output_tokens_per_request

    def estimated_cost(self, context: dict[str, object]) -> float:
        input_tokens, output_tokens = self.estimate_tokens(context)
        return (
            input_tokens * self.input_cost_per_million / 1_000_000
            + output_tokens * self.output_cost_per_million / 1_000_000
        )
