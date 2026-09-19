from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.adapters.market_data import DemoMarketDataProvider
from market_sentinel_ai.backtesting import SimpleBacktestEngine
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.features import OHLCVFeatureEngine
from market_sentinel_ai.ml import WalkForwardEvaluator, WalkForwardSplit, build_directional_examples
from market_sentinel_ai.models import LogisticDirectionalModel, MomentumBaselineModel
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

    backtest = subparsers.add_parser("backtest-demo")
    backtest.add_argument("--symbol", default="SPY")
    backtest.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    backtest.add_argument("--days", type=int, default=10)

    walk_forward = subparsers.add_parser("walk-forward-demo")
    walk_forward.add_argument("--symbol", default="SPY")
    walk_forward.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    walk_forward.add_argument("--days", type=int, default=30)
    walk_forward.add_argument("--train-size", type=int, default=500)
    walk_forward.add_argument("--test-size", type=int, default=100)

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
    if command == "backtest-demo":
        _backtest_demo(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "walk-forward-demo":
        _walk_forward_demo(
            args.symbol,
            Timeframe(args.timeframe),
            args.days,
            args.train_size,
            args.test_size,
        )
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


def _backtest_demo(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    provider = DemoMarketDataProvider()
    candles = list(provider.historical_candles(symbol, timeframe, start, end))
    engine = SimpleBacktestEngine(
        feature_engine=OHLCVFeatureEngine(rolling_window=20),
        model=MomentumBaselineModel(horizon_minutes=5),
        fee_bps=settings.risk.default_fee_bps,
        slippage_bps=settings.risk.default_slippage_bps,
    )
    report = engine.run(candles)
    print(
        json.dumps(
            {
                "symbol": symbol.upper(),
                "timeframe": timeframe.value,
                "days": days,
                "trades": report.trades,
                "win_rate": report.win_rate,
                "expectancy_bps": report.expectancy_bps,
                "profit_factor": report.profit_factor,
                "sharpe": report.sharpe,
                "sortino": report.sortino,
                "max_drawdown_pct": report.max_drawdown_pct,
                "fees_bps": settings.risk.default_fee_bps,
                "slippage_bps": settings.risk.default_slippage_bps,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _walk_forward_demo(
    symbol: str,
    timeframe: Timeframe,
    days: int,
    train_size: int,
    test_size: int,
) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    provider = DemoMarketDataProvider()
    feature_engine = OHLCVFeatureEngine(rolling_window=20)
    candles = list(provider.historical_candles(symbol, timeframe, start, end))
    examples = build_directional_examples(candles, feature_engine, horizon_candles=1)
    evaluator = WalkForwardEvaluator(
        model_factory=lambda: LogisticDirectionalModel(horizon_minutes=5, epochs=100),
        splitter=WalkForwardSplit(train_size=train_size, test_size=test_size),
    )
    report = evaluator.evaluate(examples)
    print(
        json.dumps(
            {
                "symbol": symbol.upper(),
                "timeframe": timeframe.value,
                "days": days,
                "examples": len(examples),
                "folds": len(report.folds),
                "average_accuracy": report.average_accuracy,
                "average_precision": report.average_precision,
                "average_recall": report.average_recall,
                "average_coverage": report.average_coverage,
            },
            indent=2,
            sort_keys=True,
        )
    )
