from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from market_sentinel_ai.analytics import ChartWindow, chart_window_spec
from market_sentinel_ai.api import create_app
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.operations import MarketScanService
from market_sentinel_ai.storage import SQLiteCandleRepository


class O6ChartProvider:
    provider_name = "o6-test"

    def historical_candles(self, symbol, timeframe, start, end):
        step_minutes = {
            Timeframe.ONE_MINUTE: 1,
            Timeframe.FIVE_MINUTES: 5,
            Timeframe.FIFTEEN_MINUTES: 15,
            Timeframe.ONE_HOUR: 60,
            Timeframe.ONE_DAY: 1440,
        }[timeframe]
        candles = []
        for index in range(100):
            opened_at = start + timedelta(minutes=step_minutes * index)
            if opened_at >= end:
                break
            close = 100.0 + index * 0.2
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    opened_at=opened_at,
                    open=close - 0.05,
                    high=close + 0.1,
                    low=close - 0.1,
                    close=close,
                    volume=100_000.0,
                )
            )
        return candles


class UnavailableYahooProvider:
    provider_name = "yahoo"

    def historical_candles(self, symbol, timeframe, start, end):
        return []


class O6MarketUITests(unittest.TestCase):
    def test_chart_windows_cover_requested_filters(self) -> None:
        self.assertEqual(
            [item.value for item in ChartWindow],
            [
                "1m",
                "5m",
                "30m",
                "1h",
                "6h",
                "12h",
                "1d",
                "1w",
                "1mo",
                "3mo",
                "6mo",
                "1y",
                "3y",
                "total",
            ],
        )
        self.assertEqual(chart_window_spec("1mo").timeframe, Timeframe.ONE_DAY)
        self.assertIsNone(chart_window_spec("total").lookback)

    def test_market_endpoint_returns_chart_levels_and_forecast(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            settings = replace(Settings.from_env(), database_url=f"sqlite:///{database}")
            repository = SQLiteCandleRepository(database)
            service = MarketScanService(
                settings,
                repository=repository,
                provider=O6ChartProvider(),
            )
            client = TestClient(create_app(settings, service))

            response = client.get("/api/v1/market/SPY", params={"window": "1d"})
            payload = response.json()

            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["symbol"], "SPY")
            self.assertEqual(payload["source"], "provider")
            self.assertGreater(payload["candle_count"], 2)
            self.assertEqual(len(payload["forecast"]["upper"]), 6)
            self.assertIn(payload["forecast"]["direction"], {"LONG", "SHORT", "NO_TRADE"})
            self.assertIn("entry", payload["levels"])
            self.assertIn("aproximado", payload["disclaimer"])
            model_status = client.get("/api/v1/model-status")
            self.assertEqual(model_status.status_code, 200)
            self.assertTrue(model_status.json())

            invalid = client.get("/api/v1/market/SPY", params={"window": "90d"})
            self.assertEqual(invalid.status_code, 422)

    def test_dashboard_exposes_clickable_chart_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            settings = replace(Settings.from_env(), database_url=f"sqlite:///{database}")
            repository = SQLiteCandleRepository(database)
            service = MarketScanService(
                settings,
                repository=repository,
                provider=O6ChartProvider(),
            )
            html = TestClient(create_app(settings, service)).get("/").text

            self.assertIn('id="market-chart"', html)
            self.assertIn('class="watchlist-row"', html)
            self.assertIn('data-watchlist-direction=', html)
            self.assertIn('data-window="1mo"', html)
            self.assertIn("/api/v1/market/", html)
            self.assertIn('id="scan-periodic"', html)
            self.assertIn('id="paper-metrics"', html)
            self.assertIn('id="health-status"', html)
            self.assertIn('id="model-status"', html)
            self.assertIn('id="market-decision"', html)
            self.assertIn('id="forecast-label"', html)
            self.assertIn('id="level-entry"', html)
            self.assertIn('id="level-target"', html)
            self.assertIn('id="level-stop"', html)
            self.assertIn('id="chart-tooltip"', html)
            self.assertIn("mousemove", html)
            self.assertIn('data-chart-mode="candles"', html)
            self.assertIn("Velas OHLC", html)

    def test_live_provider_does_not_fall_back_to_unlabelled_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            settings = replace(Settings.from_env(), database_url=f"sqlite:///{database}")
            repository = SQLiteCandleRepository(database)
            service = MarketScanService(
                settings,
                repository=repository,
                provider=UnavailableYahooProvider(),
            )
            response = TestClient(create_app(settings, service)).get(
                "/api/v1/market/SPY", params={"window": "1d"}
            )

            self.assertEqual(response.status_code, 503)
            self.assertIn("fresh yahoo market data is unavailable", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
