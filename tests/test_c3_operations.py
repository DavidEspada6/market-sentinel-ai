from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from market_sentinel_ai.api import create_app
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.operations import MarketScanService, MarketScheduler
from market_sentinel_ai.storage import SQLiteCandleRepository


class TrendingProvider:
    provider_name = "test-trending"

    def historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        return [
            Candle(
                symbol=symbol.upper(),
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


class RecordingAlertChannel:
    channel_name = "test-channel"

    def __init__(self) -> None:
        self.sent = 0

    def send(self, signal: object) -> str:
        self.sent += 1
        return f"test-alert-{self.sent}"


def _settings(database_path: Path) -> Settings:
    base = Settings.from_env()
    return replace(
        base,
        database_url=f"sqlite:///{database_path}",
        alerts=replace(base.alerts, dry_run=True),
    )


class C3OperationsTests(unittest.TestCase):
    def test_scan_persists_signal_and_alert(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "market.sqlite3")
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            channel = RecordingAlertChannel()
            service = MarketScanService(
                settings,
                repository=repository,
                provider=TrendingProvider(),
                alert_channel=channel,
            )

            result = service.scan("SPY", Timeframe.FIVE_MINUTES, days=1)

            self.assertEqual(result.signal.direction.value, "LONG")
            self.assertEqual(result.alerts[0].status, "sent")
            self.assertEqual(channel.sent, 1)
            self.assertEqual(len(repository.list_signals()), 1)
            self.assertEqual(len(repository.list_alerts()), 1)

    def test_scheduler_records_run_for_multiple_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "market.sqlite3")
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            service = MarketScanService(
                settings,
                repository=repository,
                provider=TrendingProvider(),
                alert_channel=RecordingAlertChannel(),
            )

            result = MarketScheduler(service, interval_seconds=1).run_once(
                ("SPY", "QQQ"), Timeframe.FIVE_MINUTES, days=1
            )

            self.assertEqual(result.run.status, "completed")
            self.assertEqual(result.run.signal_count, 2)
            self.assertEqual(len(repository.list_scheduler_runs()), 1)

    def test_api_exposes_health_scan_records_and_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = _settings(Path(directory) / "market.sqlite3")
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            service = MarketScanService(
                settings,
                repository=repository,
                provider=TrendingProvider(),
                alert_channel=RecordingAlertChannel(),
            )
            client = TestClient(create_app(settings, service))

            health = client.get("/health")
            scan = client.post(
                "/api/v1/scan",
                json={"symbol": "SPY", "timeframe": "5m", "days": 1},
            )
            signals = client.get("/api/v1/signals")
            dashboard = client.get("/")

            self.assertEqual(health.status_code, 200)
            self.assertFalse(health.json()["real_orders_enabled"])
            self.assertEqual(scan.status_code, 200)
            self.assertEqual(signals.json()[0]["symbol"], "SPY")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("Latest signals", dashboard.text)
            self.assertIn("SPY", dashboard.text)


if __name__ == "__main__":
    unittest.main()
