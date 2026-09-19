from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_sentinel_ai.adapters.market_data import DemoMarketDataProvider
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.storage import SQLiteCandleRepository


class SQLiteCandleRepositoryTests(unittest.TestCase):
    def test_upsert_is_idempotent_and_lists_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            provider = DemoMarketDataProvider()
            start = datetime(2026, 9, 18, tzinfo=UTC)
            end = start + timedelta(minutes=15)
            candles = list(provider.historical_candles("SPY", Timeframe.FIVE_MINUTES, start, end))

            self.assertEqual(repository.upsert_many(candles), 3)
            self.assertEqual(repository.upsert_many(candles), 3)
            self.assertEqual(repository.count(), 3)

            stored = repository.list_candles("SPY", Timeframe.FIVE_MINUTES, start, end)
            self.assertEqual(stored, candles)


if __name__ == "__main__":
    unittest.main()

