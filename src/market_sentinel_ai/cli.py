from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.adapters.market_data import DemoMarketDataProvider
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.releases import CURRENT_RELEASE, RELEASE_PLAN
from market_sentinel_ai.storage import SQLiteCandleRepository, sqlite_path_from_url


def main() -> None:
    parser = argparse.ArgumentParser(prog="market-sentinel")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status")

    ingest = subparsers.add_parser("demo-ingest")
    ingest.add_argument("--symbol", default="SPY")
    ingest.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    ingest.add_argument("--days", type=int, default=5)

    list_candles = subparsers.add_parser("list-candles")
    list_candles.add_argument("--symbol", default="SPY")
    list_candles.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    list_candles.add_argument("--days", type=int, default=5)

    args = parser.parse_args()
    command = args.command or "status"
    settings = Settings.from_env()
    if command == "status":
        _print_status(settings)
        return
    if command == "demo-ingest":
        _demo_ingest(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "list-candles":
        _list_candles(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    parser.error(f"unknown command: {command}")


def _print_status(settings: Settings) -> None:
    payload = {
        "app": "Market Sentinel AI",
        "environment": settings.environment,
        "astra_model": settings.openai.model,
        "astra_enabled": settings.openai.enabled,
        "current_release": CURRENT_RELEASE.code,
        "current_version": CURRENT_RELEASE.version,
        "planned_releases": [release.code for release in RELEASE_PLAN],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def _demo_ingest(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    provider = DemoMarketDataProvider()
    candles = list(provider.historical_candles(symbol, timeframe, start, end))
    accepted = repository.upsert_many(candles)
    print(
        json.dumps(
            {
                "symbol": symbol.upper(),
                "timeframe": timeframe.value,
                "accepted": accepted,
                "stored_total": repository.count(),
                "database_url": settings.database_url,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _list_candles(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    candles = repository.list_candles(symbol, timeframe, start, end)
    payload = [
        {
            "symbol": candle.symbol,
            "timeframe": candle.timeframe.value,
            "opened_at": candle.opened_at.isoformat(),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in candles[-10:]
    ]
    print(json.dumps(payload, indent=2, sort_keys=True))
