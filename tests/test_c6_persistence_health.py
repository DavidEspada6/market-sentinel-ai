from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from market_sentinel_ai.api import create_app
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal
from market_sentinel_ai.domain.risk import RiskLimits
from market_sentinel_ai.monitoring import FeatureDriftDetector, HealthService
from market_sentinel_ai.paper import PaperTradingLedger
from market_sentinel_ai.ports.features import FeatureRow
from market_sentinel_ai.storage import SQLiteCandleRepository


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


class C6PersistenceHealthTests(unittest.TestCase):
    def test_paper_ledger_recovers_equity_and_trades_from_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            ledger = PaperTradingLedger(starting_equity=100_000, store=repository)
            trade = ledger.simulate_round_trip(
                signal=_signal(),
                entry_price=100.0,
                exit_price=101.0,
                opened_at=datetime(2026, 9, 19, tzinfo=UTC),
                closed_at=datetime(2026, 9, 19, 0, 5, tzinfo=UTC),
                risk=RiskLimits(0.02, 0.03, 1, 2),
            )

            recovered = PaperTradingLedger(starting_equity=1, store=repository)
            account = repository.load_paper_account("default")

            self.assertIsNotNone(trade)
            self.assertIsNotNone(account)
            self.assertFalse(account.real_execution_enabled)
            self.assertEqual(len(recovered.trades), 1)
            self.assertEqual(recovered.equity, ledger.equity)

    def test_drift_health_and_backup_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            backup = Path(directory) / "backup.sqlite3"
            repository = SQLiteCandleRepository(database)
            report = FeatureDriftDetector(threshold=2.0).compare(
                [FeatureRow("SPY", "a", {"x": 0.0})],
                [FeatureRow("SPY", "b", {"x": 100.0})],
            )

            report_id = repository.record_drift_report("SPY", "test-model", report)
            health = HealthService(repository).check()
            repository.backup_to(backup)

            restored = SQLiteCandleRepository(backup)
            self.assertTrue(report.drifted)
            self.assertEqual(len(repository.list_drift_reports()), 1)
            self.assertTrue(report_id)
            self.assertEqual(health.status, "ok")
            self.assertEqual(restored.health_status()["status"], "ok")

    def test_api_exposes_paper_drift_and_health_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            repository = SQLiteCandleRepository(database)
            PaperTradingLedger(starting_equity=100_000, store=repository)
            base = Settings.from_env()
            settings = replace(base, database_url=f"sqlite:///{database}")
            client = TestClient(create_app(settings, service=None))

            account = client.get("/api/v1/paper/account")
            health = client.get("/api/v1/health/details")
            history = client.get("/api/v1/health/history")

            self.assertEqual(account.status_code, 200)
            self.assertFalse(account.json()["real_execution_enabled"])
            self.assertEqual(health.json()["real_orders_enabled"], False)
            self.assertGreaterEqual(len(history.json()), 0)


if __name__ == "__main__":
    unittest.main()
