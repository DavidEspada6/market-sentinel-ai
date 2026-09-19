from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from market_sentinel_ai.config import Settings
from market_sentinel_ai.context import NewsContextBuilder, RssNewsProvider
from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal
from market_sentinel_ai.reasoning import (
    AstraCostPolicy,
    AstraReasoningProvider,
    AstraUsageLedger,
    ReasoningCache,
    ReasoningGateway,
)


def _signal() -> Signal:
    return Signal(
        prediction=Prediction(
            symbol="SPY",
            horizon_minutes=5,
            direction=Direction.LONG,
            probability=0.9,
            model_name="test",
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
        ),
        confidence=0.9,
        rationale="test",
    )


class C5ContextBudgetTests(unittest.TestCase):
    def test_rss_provider_builds_compact_symbol_context(self) -> None:
        payload = b"""
        <rss><channel>
          <item>
            <title>SPY earnings context</title>
            <link>https://news.example/spy</link>
            <pubDate>Sat, 19 Sep 2026 08:00:00 GMT</pubDate>
            <description>SPY market summary</description>
          </item>
        </channel></rss>
        """
        provider = RssNewsProvider(("https://feed.example/rss",), transport=lambda _: payload)

        context = NewsContextBuilder(provider).for_symbol("SPY")

        self.assertEqual(context["news_count"], 1)
        self.assertEqual(context["news"][0]["title"], "SPY earnings context")
        self.assertEqual(context["sources"], ["news:https://feed.example/rss"])

    def test_gateway_persists_request_budget_and_cache_hits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Settings.from_env()
            settings = replace(
                base,
                openai=replace(base.openai, usage_path=str(Path(directory) / "usage.jsonl")),
            )
            provider = AstraReasoningProvider(settings.openai, ReasoningCache())
            gateway = ReasoningGateway(
                provider=provider,
                policy=AstraCostPolicy(min_confidence=0.7, max_requests_per_day=1),
                usage_ledger=AstraUsageLedger(settings.openai.usage_path),
            )
            signal = _signal()
            context = {"sources": ["test-news"], "news": [{"title": "SPY"}]}

            first = gateway.maybe_explain(signal, context)
            second = gateway.maybe_explain(signal, context)
            usage = AstraUsageLedger(settings.openai.usage_path).snapshot()

            self.assertIsNotNone(first)
            self.assertEqual(first, second)
            self.assertEqual(usage.requests, 1)
            self.assertEqual(usage.cache_hits, 1)


if __name__ == "__main__":
    unittest.main()
