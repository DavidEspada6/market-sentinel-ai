from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from market_sentinel_ai.api import create_app
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.instruments import custom_instrument
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.operations import PredictionEvaluation
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.operations import MarketScanService, PredictionMonitor
from market_sentinel_ai.paper import SimulationLedger
from market_sentinel_ai.storage import SQLiteCandleRepository


class EmptyProvider:
    provider_name = "evaluation-test"

    def historical_candles(self, symbol, timeframe, start, end):
        return []


class FailingProvider(EmptyProvider):
    def historical_candles(self, symbol, timeframe, start, end):
        raise OSError("network unavailable")


def _evaluation(now: datetime) -> PredictionEvaluation:
    return PredictionEvaluation(
        prediction_id="prediction-1",
        prediction_key="AAPL:1m:reference",
        symbol="AAPL",
        timeframe="1m",
        window="1m",
        horizon_minutes=1,
        generated_at=now - timedelta(minutes=10),
        reference_time=now - timedelta(minutes=10),
        reference_price=100.0,
        direction=Direction.LONG,
        probability=0.7,
        confidence=0.7,
        model_name="test-model",
        expected_return_bps=10.0,
        evaluation_threshold_bps=1.0,
        due_at=now - timedelta(minutes=9),
        status="pending",
        metadata={"test": True},
    )


class PredictionEvaluationTests(unittest.TestCase):
    def test_monitor_resolves_predictions_and_avoids_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            repository = SQLiteCandleRepository(database)
            now = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
            candles = [
                Candle(
                    symbol="AAPL",
                    timeframe=Timeframe.ONE_MINUTE,
                    opened_at=now - timedelta(minutes=20 - index),
                    open=100 + index * 0.05,
                    high=100.1 + index * 0.05,
                    low=99.9 + index * 0.05,
                    close=100 + index * 0.05,
                    volume=100_000,
                )
                for index in range(20)
            ]
            repository.upsert_many(candles)
            self.assertTrue(repository.record_prediction(_evaluation(now)))

            settings = replace(Settings.from_env(), database_url=f"sqlite:///{database}")
            service = MarketScanService(settings, repository=repository, provider=EmptyProvider())
            monitor = PredictionMonitor(service)

            first = monitor.run_once(now=now)
            self.assertEqual(first.resolved, 1)
            self.assertGreaterEqual(first.generated, 1)
            resolved = repository.list_predictions(status="resolved")
            self.assertTrue(resolved[0].correct)
            self.assertGreater(resolved[0].actual_return_bps or 0, 0)

            second = monitor.run_once(now=now)
            self.assertEqual(second.generated, 0)
            self.assertEqual(len(repository.list_predictions()), 2)

    def test_analysis_page_and_filters_expose_prediction_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            repository = SQLiteCandleRepository(database)
            now = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
            repository.record_prediction(_evaluation(now))
            repository.resolve_prediction(
                "prediction-1",
                actual_price=101.0,
                actual_return_bps=100.0,
                correct=True,
                resolved_at=now,
            )
            settings = replace(Settings.from_env(), database_url=f"sqlite:///{database}")
            service = MarketScanService(settings, repository=repository, provider=EmptyProvider())
            client = TestClient(create_app(settings, service))

            page = client.get("/analysis")
            response = client.get(
                "/api/v1/prediction-analytics",
                params={"symbol": "AAPL", "window": "1m"},
            )

            self.assertEqual(page.status_code, 200)
            self.assertIn("Resultado por horizonte", page.text)
            self.assertIn("/api/v1/prediction-analytics", page.text)
            self.assertIn('value="10m"', page.text)
            self.assertIn('value="2h"', page.text)
            self.assertIn('id="reset-history"', page.text)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["accuracy_pct"], 100.0)
            self.assertEqual(response.json()["best_window"], "1m")
            self.assertEqual(response.json()["by_symbol"][0]["key"], "AAPL")
            self.assertEqual(len(response.json()["recent"]), 1)
            self.assertIn("overallAccuracyClass", page.text)
            self.assertEqual(
                PredictionMonitor(service).status()["interval_seconds"],
                settings.market_data.poll_seconds,
            )

            all_results = client.get("/api/v1/prediction-analytics").json()
            self.assertEqual(
                [row["key"] for row in all_results["by_window"]],
                [
                    "1m",
                    "5m",
                    "10m",
                    "30m",
                    "1h",
                    "2h",
                    "6h",
                    "12h",
                    "1d",
                    "1w",
                    "1mo",
                    "3mo",
                    "6mo",
                    "1y",
                    "3y",
                ],
            )
            self.assertEqual(all_results["by_window"][2]["total"], 0)
            self.assertEqual(all_results["by_window"][4]["total"], 0)
            self.assertEqual(all_results["by_window"][5]["total"], 0)

            reset = client.post("/api/v1/predictions/reset")
            self.assertEqual(reset.status_code, 200)
            self.assertEqual(reset.json()["deleted"], 1)
            self.assertEqual(client.get("/api/v1/predictions").json(), [])

    def test_monitor_skips_exchange_assets_on_weekends(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            repository = SQLiteCandleRepository(database)
            saturday = datetime(2026, 9, 19, 15, 0, tzinfo=UTC)
            repository.upsert_many(
                [
                    Candle(
                        symbol="AAPL",
                        timeframe=Timeframe.ONE_MINUTE,
                        opened_at=saturday - timedelta(minutes=20 - index),
                        open=100.0 + index,
                        high=100.1 + index,
                        low=99.9 + index,
                        close=100.0 + index,
                        volume=100_000,
                    )
                    for index in range(20)
                ]
            )
            settings = replace(Settings.from_env(), database_url=f"sqlite:///{database}")
            service = MarketScanService(settings, repository=repository, provider=EmptyProvider())

            result = PredictionMonitor(service).run_once(now=saturday)

            self.assertEqual(result.generated, 0)
            self.assertEqual(repository.list_predictions(), [])

    def test_monitor_uses_cached_candles_when_provider_is_temporarily_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            repository = SQLiteCandleRepository(database)
            now = datetime.now(tz=UTC)
            repository.upsert_many(
                [
                    Candle(
                        symbol="AAPL",
                        timeframe=Timeframe.FIVE_MINUTES,
                        opened_at=now - timedelta(minutes=10 - index * 5),
                        open=100.0 + index,
                        high=100.5 + index,
                        low=99.5 + index,
                        close=100.2 + index,
                        volume=100_000,
                    )
                    for index in range(3)
                ]
            )
            repository.add_watchlist_item(custom_instrument("AAPL"))
            settings = replace(Settings.from_env(), database_url=f"sqlite:///{database}")
            service = MarketScanService(settings, repository=repository, provider=FailingProvider())

            result = PredictionMonitor(service).run_once(now=now)

            self.assertGreater(result.generated, 0)
            self.assertTrue(any("using cached candles" in error for error in result.errors))
            self.assertLess(result.finished_at - result.started_at, timedelta(seconds=10))

    def test_simulation_trade_keeps_cost_and_leverage_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            ledger = SimulationLedger(starting_equity=10_000, store=repository)
            position = ledger.open_position(
                symbol="AAPL",
                direction=Direction.LONG,
                margin=1_000,
                leverage=5,
                entry_price=100,
            )
            trade = ledger.close_position(position.position_id, 101)
            saved = repository.list_paper_trades("simulation")[0].trade

            self.assertEqual(trade.leverage, 5)
            self.assertEqual(saved.margin, 1_000)
            self.assertEqual(saved.leverage, 5)
            self.assertGreater(saved.entry_cost + saved.exit_cost, 0)
            self.assertEqual(saved.close_reason, "manual")


if __name__ == "__main__":
    unittest.main()
