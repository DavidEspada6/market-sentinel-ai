from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from market_sentinel_ai.api import create_app
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.instruments import custom_instrument, search_instruments
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.operations import MarketScanService
from market_sentinel_ai.storage import SQLiteCandleRepository


class O1TrendingProvider:
    provider_name = "o1-test"

    def historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
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


def _settings(database: Path) -> Settings:
    return replace(Settings.from_env(), database_url=f"sqlite:///{database}")


class O1UniverseWatchlistTests(unittest.TestCase):
    def test_catalog_search_and_persistent_watchlist(self) -> None:
        self.assertEqual(search_instruments("nvidia")[0].symbol, "NVDA")

        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            initial_symbols = {item.symbol for item in repository.list_watchlist()}
            repository.add_watchlist_item(custom_instrument("my-stock"))
            repository.remove_watchlist_item("SPY")

            self.assertIn("my-stock".upper(), {item.symbol for item in repository.list_watchlist()})
            self.assertIn("SPY", initial_symbols)
            self.assertNotIn("SPY", {item.symbol for item in repository.list_watchlist()})

    def test_api_search_add_remove_dashboard_and_watchlist_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            repository = SQLiteCandleRepository(database)
            settings = _settings(database)
            service = MarketScanService(
                settings,
                repository=repository,
                provider=O1TrendingProvider(),
            )
            client = TestClient(create_app(settings, service))

            search = client.get("/api/v1/instruments", params={"q": "nvidia"})
            added = client.post("/api/v1/watchlist", json={"symbol": "CUSTOM-USD"})
            watchlist = client.get("/api/v1/watchlist")
            dashboard = client.get("/")
            scan = client.post(
                "/api/v1/watchlist/scan",
                json={"timeframe": "5m", "days": 1},
            )
            removed = client.delete("/api/v1/watchlist/CUSTOM-USD")

            self.assertEqual(search.status_code, 200)
            self.assertEqual(search.json()[0]["symbol"], "NVDA")
            self.assertEqual(added.status_code, 200)
            self.assertIn("CUSTOM-USD", {item["symbol"] for item in watchlist.json()})
            self.assertIn("instrument-search", dashboard.text)
            self.assertIn("Watchlist", dashboard.text)
            self.assertEqual(scan.status_code, 200)
            self.assertGreaterEqual(scan.json()["run"]["signal_count"], 14)
            self.assertFalse(client.get("/api/v1/status").json()["real_orders_enabled"])
            self.assertEqual(removed.status_code, 200)


if __name__ == "__main__":
    unittest.main()
