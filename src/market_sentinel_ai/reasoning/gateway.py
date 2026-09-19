from __future__ import annotations

from dataclasses import dataclass

from market_sentinel_ai.domain.prediction import Signal
from market_sentinel_ai.domain.reasoning import ReasoningResult
from market_sentinel_ai.ports.reasoning import ReasoningProvider
from market_sentinel_ai.reasoning.policy import AstraCostPolicy
from market_sentinel_ai.reasoning.usage import AstraUsageLedger


@dataclass
class ReasoningGateway:
    provider: ReasoningProvider
    policy: AstraCostPolicy
    requests_used_today: int = 0
    usage_ledger: AstraUsageLedger | None = None

    def maybe_explain(self, signal: Signal, context: dict[str, object]) -> ReasoningResult | None:
        cache_hit = _provider_has_cached(self.provider, signal, context)
        usage = self.usage_ledger.snapshot() if self.usage_ledger is not None else None
        requests_used = usage.requests if usage is not None else self.requests_used_today
        cost_used = usage.estimated_cost_usd if usage is not None else 0.0
        if not cache_hit and not self.policy.should_request_context(
            signal,
            requests_used,
            estimated_cost_used_today=cost_used,
            context=context,
        ):
            if self.usage_ledger is not None:
                self.usage_ledger.record(
                    status="blocked",
                    signal_id=signal.prediction.symbol,
                    input_tokens_estimate=0,
                    output_tokens_estimate=0,
                    estimated_cost_usd=0.0,
                )
            return None
        result = self.provider.explain_signal(signal, context)
        if not cache_hit:
            self.requests_used_today += 1
        if self.usage_ledger is not None:
            input_tokens, output_tokens = self.policy.estimate_tokens(context)
            self.usage_ledger.record(
                status="cache_hit" if cache_hit else "requested",
                signal_id=result.signal_id,
                input_tokens_estimate=0 if cache_hit else input_tokens,
                output_tokens_estimate=0 if cache_hit else output_tokens,
                estimated_cost_usd=0.0 if cache_hit else self.policy.estimated_cost(context),
            )
        return result


def _provider_has_cached(
    provider: ReasoningProvider,
    signal: Signal,
    context: dict[str, object],
) -> bool:
    has_cached = getattr(provider, "has_cached", None)
    return bool(has_cached(signal, context)) if callable(has_cached) else False
