from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from market_sentinel_ai.api import create_app
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.paper import SimulationLedger
from market_sentinel_ai.storage import SQLiteCandleRepository


class SimulationTests(unittest.TestCase):
    def test_leveraged_long_and_short_pnl_recover_from_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            ledger = SimulationLedger(starting_equity=10_000, store=repository)
            long_position = ledger.open_position(
                symbol="AAPL",
                direction=Direction.LONG,
                margin=1_000,
                leverage=5,
                entry_price=100,
            )
            ledger.mark_price(long_position.position_id, 102)
            self.assertGreater(ledger.unrealized_pnl, 90)

            recovered = SimulationLedger(starting_equity=1, store=repository)
            self.assertEqual(len(recovered.positions), 1)
            long_trade = recovered.close_position(long_position.position_id, 102)
            self.assertGreater(long_trade.pnl, 90)

            short_position = recovered.open_position(
                symbol="AAPL",
                direction=Direction.SHORT,
                margin=500,
                leverage=2,
                entry_price=100,
            )
            short_trade = recovered.close_position(short_position.position_id, 95)
            self.assertGreater(short_trade.pnl, 40)
            self.assertFalse(repository.list_paper_positions("simulation"))

    def test_api_opens_marks_closes_and_resets_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "market.sqlite3"
            settings = replace(Settings.from_env(), database_url=f"sqlite:///{database}")
            client = TestClient(create_app(settings))
            status = client.get("/api/v1/status")
            self.assertTrue(status.json()["simulation_enabled"])
            self.assertFalse(status.json()["real_orders_enabled"])

            opened = client.post(
                "/api/v1/simulation/positions",
                json={
                    "symbol": "SPY",
                    "direction": "LONG",
                    "margin": 1_000,
                    "leverage": 3,
                    "price": 100,
                },
            )
            self.assertEqual(opened.status_code, 200)
            position = opened.json()["position"]
            self.assertEqual(position["direction"], "LONG")
            self.assertEqual(position["leverage"], 3)

            account = client.get("/api/v1/simulation/account")
            self.assertEqual(account.status_code, 200)
            self.assertEqual(len(account.json()["positions"]), 1)
            self.assertFalse(account.json()["real_orders_enabled"])

            closed = client.post(
                f"/api/v1/simulation/positions/{position['position_id']}/close",
                json={"price": 101},
            )
            self.assertEqual(closed.status_code, 200)
            self.assertGreater(closed.json()["trade"]["pnl"], 0)

            metrics = client.get("/api/v1/simulation/metrics")
            self.assertEqual(metrics.status_code, 200)
            self.assertIn("var_95", metrics.json())
            self.assertGreater(metrics.json()["total_pnl"], 0)

            reset = client.post("/api/v1/simulation/reset", json={"starting_equity": 25_000})
            self.assertEqual(reset.status_code, 200)
            self.assertEqual(reset.json()["starting_equity"], 25_000)
            self.assertEqual(client.get("/api/v1/simulation/trades").json(), [])

    def test_reset_is_blocked_with_open_positions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            ledger = SimulationLedger(starting_equity=10_000, store=repository)
            ledger.open_position(
                symbol="BTC-USD",
                direction=Direction.SHORT,
                margin=500,
                leverage=2,
                entry_price=100,
            )
            with self.assertRaises(ValueError):
                ledger.reset(20_000)

    def test_refresh_auto_closes_a_position_at_simulated_liquidation(self) -> None:
        ledger = SimulationLedger(starting_equity=10_000)
        ledger.open_position(
            symbol="AAPL",
            direction=Direction.LONG,
            margin=1_000,
            leverage=10,
            entry_price=100,
        )
        ledger.refresh_prices({"AAPL": 90})
        self.assertFalse(ledger.positions)
        self.assertEqual(len(ledger.trades), 1)
        self.assertLess(ledger.trades[0].pnl, -900)


if __name__ == "__main__":
    unittest.main()
