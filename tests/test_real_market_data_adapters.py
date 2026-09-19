from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_sentinel_ai.adapters.market_data import (
    AlphaVantageMarketDataProvider,
    MarketDataProviderError,
    StooqMarketDataProvider,
    YahooFinanceMarketDataProvider,
)
from market_sentinel_ai.data_quality import analyze_candle_sequence
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.ingestion import MarketDataIngestionService
from market_sentinel_ai.storage import SQLiteCandleRepository


class RealMarketDataAdapterTests(unittest.TestCase):
    def test_stooq_parses_and_orders_daily_csv(self) -> None:
        csv_payload = (
            b"Date,Open,High,Low,Close,Volume\n"
            b"2026-09-18,101,103,100,102,1200\n"
            b"2026-09-17,100,102,99,101,1000\n"
        )
        requested: list[str] = []

        def transport(url: str) -> bytes:
            requested.append(url)
            return csv_payload

        provider = StooqMarketDataProvider(transport=transport)
        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.ONE_DAY,
                datetime(2026, 9, 17, tzinfo=UTC),
                datetime(2026, 9, 19, tzinfo=UTC),
            )
        )

        self.assertEqual([candle.close for candle in candles], [101.0, 102.0])
        self.assertIn("s=spy.us", requested[0])
        self.assertEqual(provider.provider_name, "stooq")

    def test_alpha_vantage_parses_intraday_json_as_utc(self) -> None:
        payload = {
            "Meta Data": {"6. Time Zone": "UTC"},
            "Time Series (5min)": {
                "2026-09-18 14:35:00": {
                    "1. open": "101",
                    "2. high": "102",
                    "3. low": "100.5",
                    "4. close": "101.5",
                    "5. volume": "900",
                },
                "2026-09-18 14:30:00": {
                    "1. open": "100",
                    "2. high": "101.5",
                    "3. low": "99.5",
                    "4. close": "101",
                    "5. volume": "1000",
                },
            },
        }
        provider = AlphaVantageMarketDataProvider(
            "test-key", transport=lambda _: json.dumps(payload).encode()
        )
        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.FIVE_MINUTES,
                datetime(2026, 9, 18, 14, 0, tzinfo=UTC),
                datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
            )
        )

        self.assertEqual(len(candles), 2)
        self.assertLess(candles[0].opened_at, candles[1].opened_at)
        self.assertEqual(candles[0].opened_at.tzinfo, UTC)

    def test_alpha_vantage_surfaces_rate_limit_message(self) -> None:
        provider = AlphaVantageMarketDataProvider(
            "test-key",
            transport=lambda _: json.dumps({"Note": "rate limit reached"}).encode(),
        )
        with self.assertRaisesRegex(MarketDataProviderError, "rate limit"):
            list(
                provider.historical_candles(
                    "SPY",
                    Timeframe.ONE_DAY,
                    datetime(2026, 9, 1, tzinfo=UTC),
                    datetime(2026, 9, 19, tzinfo=UTC),
                )
            )

    def test_alpha_vantage_parses_daily_date_keys(self) -> None:
        payload = {
            "Meta Data": {"5. Time Zone": "UTC"},
            "Time Series (Daily)": {
                "2026-09-18": {
                    "1. open": "100",
                    "2. high": "102",
                    "3. low": "99",
                    "4. close": "101",
                    "5. volume": "1000",
                }
            },
        }
        provider = AlphaVantageMarketDataProvider(
            "test-key", transport=lambda _: json.dumps(payload).encode()
        )

        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.ONE_DAY,
                datetime(2026, 9, 18, tzinfo=UTC),
                datetime(2026, 9, 19, tzinfo=UTC),
            )
        )

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].opened_at, datetime(2026, 9, 18, tzinfo=UTC))

    def test_yahoo_parses_chart_response(self) -> None:
        start = datetime(2026, 9, 18, 14, 30, tzinfo=UTC)
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": [int(start.timestamp()), int(start.timestamp()) + 300],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [100.0, 101.0],
                                    "high": [102.0, 103.0],
                                    "low": [99.0, 100.0],
                                    "close": [101.0, 102.0],
                                    "volume": [1000, 1100],
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }
        provider = YahooFinanceMarketDataProvider(
            transport=lambda _: json.dumps(payload).encode()
        )

        candles = list(
            provider.historical_candles(
                "SPY",
                Timeframe.FIVE_MINUTES,
                start,
                start + timedelta(minutes=10),
            )
        )

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[-1].close, 102.0)
        self.assertEqual(provider.provider_name, "yahoo")

    def test_stooq_rejects_browser_verification_page(self) -> None:
        provider = StooqMarketDataProvider(
            transport=lambda _: b"<!DOCTYPE html><body>verify browser</body>"
        )
        with self.assertRaisesRegex(MarketDataProviderError, "browser-verification"):
            list(
                provider.historical_candles(
                    "SPY",
                    Timeframe.ONE_DAY,
                    datetime(2026, 9, 1, tzinfo=UTC),
                    datetime(2026, 9, 19, tzinfo=UTC),
                )
            )

    def test_ingestion_records_quality_and_provenance(self) -> None:
        provider = StooqMarketDataProvider(
            transport=lambda _: (
                b"Date,Open,High,Low,Close,Volume\n"
                b"2026-09-17,100,102,99,101,1000\n"
                b"2026-09-18,101,103,100,102,1200\n"
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            result = MarketDataIngestionService(provider, repository).ingest(
                "SPY",
                Timeframe.ONE_DAY,
                datetime(2026, 9, 17, tzinfo=UTC),
                datetime(2026, 9, 19, tzinfo=UTC),
            )

            self.assertEqual(result.run.status, "completed")
            self.assertEqual(result.run.provider, "stooq")
            self.assertEqual(repository.count(), 2)
            self.assertEqual(repository.list_ingestion_runs()[0].run_id, result.run.run_id)

    def test_failed_ingestion_is_recorded_without_partial_data(self) -> None:
        class EmptyProvider:
            provider_name = "empty"

            def historical_candles(self, symbol, timeframe, start, end):
                return []

            def stream_candles(self, symbol, timeframe):
                return iter(())

        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteCandleRepository(Path(directory) / "market.sqlite3")
            service = MarketDataIngestionService(EmptyProvider(), repository)

            with self.assertRaisesRegex(ValueError, "quality gates"):
                service.ingest(
                    "SPY",
                    Timeframe.ONE_DAY,
                    datetime(2026, 9, 17, tzinfo=UTC),
                    datetime(2026, 9, 19, tzinfo=UTC),
                )

            self.assertEqual(repository.count(), 0)
            self.assertEqual(repository.list_ingestion_runs()[0].status, "failed")

    def test_quality_report_detects_intraday_gap(self) -> None:
        start = datetime(2026, 9, 18, 14, 30, tzinfo=UTC)
        candles = [
            Candle("SPY", Timeframe.FIVE_MINUTES, start, 100, 101, 99, 100.5, 1000),
            Candle(
                "SPY",
                Timeframe.FIVE_MINUTES,
                start + timedelta(minutes=15),
                100.5,
                102,
                100,
                101,
                1100,
            ),
        ]

        report = analyze_candle_sequence(candles, observed_at=start + timedelta(minutes=20))

        self.assertEqual(report.missing_intervals, 2)
        self.assertTrue(report.accepted)


if __name__ == "__main__":
    unittest.main()
