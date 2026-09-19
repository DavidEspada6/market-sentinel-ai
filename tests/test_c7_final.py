from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from market_sentinel_ai.api import create_app
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal
from market_sentinel_ai.domain.risk import RiskLimits
from market_sentinel_ai.monitoring import FeatureDriftDetector, HealthService
from market_sentinel_ai.operations import MarketScanService
from market_sentinel_ai.paper import PaperTradingLedger
from market_sentinel_ai.security import run_security_checks
from market_sentinel_ai.storage import SQLiteCandleRepository


class C7TrendingProvider:
    provider_name = "c7-test"

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


class C7AlertChannel:
    channel_name = "c7-dry-run"

    def send(self, signal: object) -> str:
        return "c7-alert"


def _settings(database: Path) -> Settings:
    base = Settings.from_env()
    return replace(base, database_url=f"sqlite:///{database}")


def _paper_signal() -> Signal:
    return Signal(
        prediction=Prediction(
            symbol="SPY",
            horizon_minutes=5,
            direction=Direction.LONG,
            probability=0.9,
            model_name="c7-test",
            generated_at=datetime(2026, 9, 19, tzinfo=UTC),
        ),
        confidence=0.9,
        rationale="C7 integration test",
    )


class C7FinalTests(unittest.TestCase):
    def test_repository_security_gate_is_clean(self) -> None:
        report = run_security_checks(Path(__file__).parents[1])

        self.assertEqual(report.status, "ok")
        self.assertFalse(report.findings)
        self.assertFalse(report.real_orders_enabled)
        self.assertIn("SECURITY.md", report.required_files)

    def test_end_to_end_scan_paper_drift_health_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "market.sqlite3"
            repository = SQLiteCandleRepository(database)
            settings = _settings(database)
            service = MarketScanService(
                settings,
                repository=repository,
                provider=C7TrendingProvider(),
                alert_channel=C7AlertChannel(),
            )
            client = TestClient(create_app(settings, service))

            scan = client.post(
                "/api/v1/scan",
                json={"symbol": "SPY", "timeframe": "5m", "days": 1},
            )
            ledger = PaperTradingLedger(starting_equity=100_000, store=repository)
            ledger.simulate_round_trip(
                signal=_paper_signal(),
                entry_price=100.0,
                exit_price=101.0,
                opened_at=datetime(2026, 9, 19, tzinfo=UTC),
                closed_at=datetime(2026, 9, 19, 0, 5, tzinfo=UTC),
                risk=RiskLimits(0.02, 0.03, 1, 2),
            )
            drift = FeatureDriftDetector(threshold=2.0).compare(
                [self._feature("a", 0.0)], [self._feature("b", 100.0)]
            )
            repository.record_drift_report("SPY", "c7-test", drift)
            HealthService(repository).check()
            backup = repository.backup_to(root / "backup.sqlite3")

            self.assertEqual(scan.status_code, 200)
            self.assertEqual(scan.json()["alerts"][0]["status"], "sent")
            self.assertEqual(client.get("/api/v1/signals").status_code, 200)
            self.assertEqual(len(client.get("/api/v1/paper/trades").json()), 1)
            self.assertFalse(client.get("/api/v1/paper/account").json()["real_execution_enabled"])
            self.assertEqual(len(client.get("/api/v1/drift").json()), 1)
            self.assertEqual(client.get("/api/v1/health/details").json()["status"], "ok")
            self.assertGreaterEqual(len(client.get("/api/v1/health/history").json()), 1)
            self.assertFalse(client.get("/health").json()["real_orders_enabled"])
            self.assertTrue(backup.is_file())

    @staticmethod
    def _feature(timestamp: str, value: float):
        from market_sentinel_ai.ports.features import FeatureRow

        return FeatureRow("SPY", timestamp, {"x": value})


if __name__ == "__main__":
    unittest.main()
