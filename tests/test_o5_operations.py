from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.operations import MarketScanService
from market_sentinel_ai.storage import SQLiteCandleRepository


class O5TrendingProvider:
    provider_name = "o5-test"

    def historical_candles(self, symbol, timeframe, start, end):
        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                opened_at=start + timedelta(minutes=5 * index),
                open=100.0 + index * 0.1,
                high=100.11 + index * 0.1,
                low=99.99 + index * 0.1,
                close=100.1 + index * 0.1,
                volume=100_000.0,
            )
            for index in range(60)
        ]


class O5AlertChannel:
    channel_name = "o5-test"

    def __init__(self) -> None:
        self.sent = 0

    def send(self, signal: object) -> str:
        self.sent += 1
        return f"alert-{self.sent}"


class O5OperationsTests(unittest.TestCase):
    def test_identical_actionable_scans_are_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            base = Settings.from_env()
            settings = replace(base, database_url=f"sqlite:///{database}")
            repository = SQLiteCandleRepository(database)
            channel = O5AlertChannel()
            service = MarketScanService(
                settings,
                repository=repository,
                provider=O5TrendingProvider(),
                alert_channel=channel,
            )

            first = service.scan("SPY", Timeframe.FIVE_MINUTES, days=1)
            second = service.scan("SPY", Timeframe.FIVE_MINUTES, days=1)

            self.assertEqual(first.alerts[0].status, "sent")
            self.assertEqual(second.alerts[0].status, "suppressed")
            self.assertEqual(channel.sent, 1)
            self.assertEqual(len(repository.list_alerts()), 2)


if __name__ == "__main__":
    unittest.main()
