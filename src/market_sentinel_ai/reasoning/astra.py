from __future__ import annotations

import json
from datetime import UTC, datetime

from market_sentinel_ai.config import OpenAISettings
from market_sentinel_ai.domain.prediction import Signal
from market_sentinel_ai.domain.reasoning import ReasoningResult
from market_sentinel_ai.reasoning.cache import ReasoningCache
from market_sentinel_ai.reasoning.schema import ASTRA_REASONING_JSON_SCHEMA


class AstraReasoningProvider:
    def __init__(self, settings: OpenAISettings, cache: ReasoningCache) -> None:
        self.settings = settings
        self.cache = cache
        self.last_cache_hit = False

    def has_cached(self, signal: Signal, context: dict[str, object]) -> bool:
        return self.cache.get(self.cache.key_for(signal, context)) is not None

    def explain_signal(self, signal: Signal, context: dict[str, object]) -> ReasoningResult:
        self.last_cache_hit = False
        cache_key = self.cache.key_for(signal, context)
        cached = self.cache.get(cache_key)
        if cached is not None:
            self.last_cache_hit = True
            return cached

        if not self.settings.enabled:
            result = self._fallback(signal, context, "OPENAI_API_KEY is not configured.")
            self.cache.set(cache_key, result)
            return result

        result = self._call_openai(signal, context)
        self.cache.set(cache_key, result)
        return result

    def _call_openai(self, signal: Signal, context: dict[str, object]) -> ReasoningResult:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install market-sentinel-ai[openai] to call GPT-6 Astra.") from exc

        client = OpenAI(api_key=self.settings.api_key)
        prompt = {
            "signal": {
                "symbol": signal.prediction.symbol,
                "direction": signal.prediction.direction.value,
                "confidence": signal.confidence,
                "probability": signal.prediction.probability,
                "model_name": signal.prediction.model_name,
                "expected_return_bps": signal.prediction.expected_return_bps,
                "risk_notes": list(signal.risk_notes),
            },
            "context": context,
        }
        response = client.responses.create(
            model=self.settings.model,
            reasoning={"effort": self.settings.reasoning_effort},
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a market-context reasoning layer. Return concise structured "
                        "risk context for an already-gated quantitative signal. Do not claim "
                        "certainty and do not bypass risk limits."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, sort_keys=True)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "market_signal_reasoning",
                    "schema": ASTRA_REASONING_JSON_SCHEMA,
                    "strict": True,
                }
            },
            max_output_tokens=self.settings.max_output_tokens_per_request,
        )
        payload = json.loads(response.output_text)
        return _validated_result(
            signal_id=self.cache.signal_id(signal),
            generated_at=datetime.now(tz=UTC),
            payload=payload,
            raw_cost_tokens_estimate=_response_token_estimate(response),
        )

    def _fallback(self, signal: Signal, context: dict[str, object], reason: str) -> ReasoningResult:
        sources = [str(item) for item in context.get("sources", [])]
        return ReasoningResult(
            signal_id=self.cache.signal_id(signal),
            generated_at=datetime.now(tz=UTC),
            thesis=f"Astra reasoning skipped: {reason}",
            invalidation="Configure OPENAI_API_KEY and pass the cost gate to request live context.",
            risk_notes=(
                "Fallback explanation only; no model call was made.",
                "Quantitative risk limits remain authoritative.",
            ),
            context_sources=tuple(sources),
            raw_cost_tokens_estimate=0,
        )


def _validated_result(
    *,
    signal_id: str,
    generated_at: datetime,
    payload: object,
    raw_cost_tokens_estimate: int | None,
) -> ReasoningResult:
    if not isinstance(payload, dict):
        raise ValueError("Astra response must be a JSON object")
    required = ("thesis", "invalidation", "risk_notes", "context_sources")
    if any(key not in payload for key in required):
        raise ValueError("Astra response is missing required structured fields")
    if not isinstance(payload["thesis"], str) or not isinstance(payload["invalidation"], str):
        raise ValueError("Astra thesis and invalidation must be strings")
    if not isinstance(payload["risk_notes"], list) or not all(
        isinstance(item, str) for item in payload["risk_notes"]
    ):
        raise ValueError("Astra risk_notes must be a list of strings")
    if not isinstance(payload["context_sources"], list) or not all(
        isinstance(item, str) for item in payload["context_sources"]
    ):
        raise ValueError("Astra context_sources must be a list of strings")
    return ReasoningResult(
        signal_id=signal_id,
        generated_at=generated_at,
        thesis=payload["thesis"],
        invalidation=payload["invalidation"],
        risk_notes=tuple(payload["risk_notes"]),
        context_sources=tuple(payload["context_sources"]),
        raw_cost_tokens_estimate=raw_cost_tokens_estimate,
    )


def _response_token_estimate(response: object) -> int | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    return int(input_tokens) + int(output_tokens)
