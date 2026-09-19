from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal
from market_sentinel_ai.reasoning import (
    ASTRA_REASONING_JSON_SCHEMA,
    AstraReasoningProvider,
    ReasoningCache,
)


def _signal() -> Signal:
    return Signal(
        prediction=Prediction(
            symbol="SPY",
            horizon_minutes=5,
            direction=Direction.LONG,
            probability=0.82,
            model_name="test",
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
            expected_return_bps=6.0,
        ),
        confidence=0.82,
        rationale="test",
    )


class AstraReasoningTests(unittest.TestCase):
    def test_schema_requires_auditable_fields(self) -> None:
        self.assertEqual(ASTRA_REASONING_JSON_SCHEMA["type"], "object")
        self.assertIn("thesis", ASTRA_REASONING_JSON_SCHEMA["required"])
        self.assertIn("risk_notes", ASTRA_REASONING_JSON_SCHEMA["required"])

    def test_provider_returns_cached_no_key_fallback(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            settings = Settings.from_env()
        cache = ReasoningCache()
        provider = AstraReasoningProvider(settings.openai, cache)
        signal = _signal()
        context = {"sources": ["unit-test"]}

        first = provider.explain_signal(signal, context)
        second = provider.explain_signal(signal, context)

        self.assertEqual(first, second)
        self.assertEqual(first.raw_cost_tokens_estimate, 0)
        self.assertIn("unit-test", first.context_sources)


if __name__ == "__main__":
    unittest.main()

