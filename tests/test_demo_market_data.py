from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.adapters.market_data import DemoMarketDataProvider
from market_sentinel_ai.data_quality import validate_candle_sequence
from market_sentinel_ai.domain.market import Timeframe


class DemoMarketDataProviderTests(unittest.TestCase):
    def test_historical_candles_are_deterministic_and_ordered(self) -> None:
        provider = DemoMarketDataProvider()
        start = datetime(2026, 9, 18, tzinfo=UTC)
        end = start + timedelta(minutes=15)

        first = list(provider.historical_candles("spy", Timeframe.FIVE_MINUTES, start, end))
        second = list(provider.historical_candles("spy", Timeframe.FIVE_MINUTES, start, end))

        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertEqual(first[0].symbol, "SPY")
        validate_candle_sequence(first)


if __name__ == "__main__":
    unittest.main()

