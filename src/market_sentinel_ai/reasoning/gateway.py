from __future__ import annotations

from dataclasses import dataclass

from market_sentinel_ai.domain.prediction import Signal
from market_sentinel_ai.domain.reasoning import ReasoningResult
from market_sentinel_ai.ports.reasoning import ReasoningProvider
from market_sentinel_ai.reasoning.policy import AstraCostPolicy


@dataclass
class ReasoningGateway:
    provider: ReasoningProvider
    policy: AstraCostPolicy
    requests_used_today: int = 0

    def maybe_explain(self, signal: Signal, context: dict[str, object]) -> ReasoningResult | None:
        if not self.policy.should_request_context(signal, self.requests_used_today):
            return None
        self.requests_used_today += 1
        return self.provider.explain_signal(signal, context)

