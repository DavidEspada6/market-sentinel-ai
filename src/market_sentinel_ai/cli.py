from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_sentinel_ai.adapters.market_data import (
    DemoMarketDataProvider,
    DemoOrderBookProvider,
    build_market_data_provider,
    build_order_book_provider,
)
from market_sentinel_ai.alerts import DryRunAlertChannel
from market_sentinel_ai.backtesting import SimpleBacktestEngine
from market_sentinel_ai.config import Settings
from market_sentinel_ai.context import NewsContextBuilder, NewsItem, StaticNewsProvider
from market_sentinel_ai.dashboard import DashboardViewModel, render_dashboard
from market_sentinel_ai.domain.instruments import (
    AssetClass,
    custom_instrument,
    find_instrument,
    search_instruments,
)
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.domain.risk import RiskLimits
from market_sentinel_ai.features import (
    AlignedMultiTimeframeFeatureEngine,
    OHLCVFeatureEngine,
    OrderFlowFeatureEngine,
    aggregate_candles,
)
from market_sentinel_ai.ingestion import MarketDataIngestionService
from market_sentinel_ai.ml import WalkForwardEvaluator, WalkForwardSplit, build_directional_examples
from market_sentinel_ai.models import (
    LightGBMDirectionalModel,
    LogisticDirectionalModel,
    MomentumBaselineModel,
    RegimeAwareEnsembleModel,
    WeightedModel,
    XGBoostDirectionalModel,
)
from market_sentinel_ai.monitoring import FeatureDriftDetector, HealthService, JsonlEventLogger
from market_sentinel_ai.operations import MarketScanService, MarketScheduler
from market_sentinel_ai.paper import PaperTradingLedger
from market_sentinel_ai.reasoning import (
    AstraCostPolicy,
    AstraReasoningProvider,
    AstraUsageLedger,
    ReasoningCache,
    ReasoningGateway,
)
from market_sentinel_ai.regime import Regime
from market_sentinel_ai.releases import (
    COMPLETION_PLAN,
    CURRENT_RELEASE,
    FOLLOW_ON_PLAN,
    RELEASE_PLAN,
)
from market_sentinel_ai.security import run_security_checks
from market_sentinel_ai.signals import SignalEngine
from market_sentinel_ai.storage import SQLiteCandleRepository, sqlite_path_from_url


def main() -> None:
    parser = argparse.ArgumentParser(prog="market-sentinel")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status")

    ingest = subparsers.add_parser("demo-ingest")
    ingest.add_argument("--symbol", default="SPY")
    ingest.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    ingest.add_argument("--days", type=int, default=5)

    provider_ingest = subparsers.add_parser("ingest")
    provider_ingest.add_argument(
        "--provider", choices=["demo", "yahoo", "stooq", "alpha_vantage"]
    )
    provider_ingest.add_argument("--symbol", default="SPY")
    provider_ingest.add_argument(
        "--timeframe", choices=[item.value for item in Timeframe], default="1d"
    )
    provider_ingest.add_argument("--days", type=int, default=365)

    ingestion_runs = subparsers.add_parser("ingestion-runs")
    ingestion_runs.add_argument("--limit", type=int, default=20)

    list_candles = subparsers.add_parser("list-candles")
    list_candles.add_argument("--symbol", default="SPY")
    list_candles.add_argument(
        "--timeframe", choices=[item.value for item in Timeframe], default="5m"
    )
    list_candles.add_argument("--days", type=int, default=5)

    backtest = subparsers.add_parser("backtest-demo")
    backtest.add_argument("--symbol", default="SPY")
    backtest.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    backtest.add_argument("--days", type=int, default=10)

    walk_forward = subparsers.add_parser("walk-forward-demo")
    walk_forward.add_argument("--symbol", default="SPY")
    walk_forward.add_argument(
        "--timeframe", choices=[item.value for item in Timeframe], default="5m"
    )
    walk_forward.add_argument("--days", type=int, default=30)
    walk_forward.add_argument("--train-size", type=int, default=500)
    walk_forward.add_argument("--test-size", type=int, default=100)
    walk_forward.add_argument(
        "--model", choices=["logistic", "xgboost", "lightgbm"], default="logistic"
    )

    boosting = subparsers.add_parser("boosting-demo")
    boosting.add_argument("--backend", choices=["xgboost", "lightgbm"], default="xgboost")
    boosting.add_argument("--symbol", default="SPY")
    boosting.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    boosting.add_argument("--days", type=int, default=5)
    boosting.add_argument("--output", default="models/demo-boosting")

    signals = subparsers.add_parser("signals-demo")
    signals.add_argument("--symbol", default="SPY")
    signals.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    signals.add_argument("--days", type=int, default=10)

    dashboard = subparsers.add_parser("dashboard-demo")
    dashboard.add_argument("--symbol", default="SPY")
    dashboard.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    dashboard.add_argument("--days", type=int, default=30)
    dashboard.add_argument("--output", default="reports/dashboard.html")

    ensemble = subparsers.add_parser("ensemble-demo")
    ensemble.add_argument("--symbol", default="SPY")
    ensemble.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    ensemble.add_argument("--days", type=int, default=20)

    order_book = subparsers.add_parser("order-book-demo")
    order_book.add_argument("--provider", choices=["demo", "binance"])
    order_book.add_argument("--symbol", default="BTCUSDT")
    order_book.add_argument("--depth", type=int, default=5)

    astra = subparsers.add_parser("astra-context-demo")
    astra.add_argument("--symbol", default="SPY")
    astra.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    astra.add_argument("--days", type=int, default=10)

    news = subparsers.add_parser("news-demo")
    news.add_argument("--provider", choices=["demo", "rss"], default="demo")
    news.add_argument("--symbol", default="SPY")
    news.add_argument("--limit", type=int, default=5)
    news.add_argument("--feed-url", action="append", default=[])

    paper = subparsers.add_parser("paper-demo")
    paper.add_argument("--symbol", default="SPY")
    paper.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    paper.add_argument("--days", type=int, default=10)

    drift = subparsers.add_parser("drift-demo")
    drift.add_argument("--symbol", default="SPY")
    drift.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    drift.add_argument("--days", type=int, default=20)

    subparsers.add_parser("health")

    subparsers.add_parser("security-check")

    instruments = subparsers.add_parser("instruments")
    instruments.add_argument("--query", default="")
    instruments.add_argument("--asset-class", choices=[item.value for item in AssetClass])
    instruments.add_argument("--limit", type=int, default=50)

    watchlist = subparsers.add_parser("watchlist")
    watchlist_group = watchlist.add_mutually_exclusive_group()
    watchlist_group.add_argument("--add")
    watchlist_group.add_argument("--remove")

    watchlist_scan = subparsers.add_parser("watchlist-scan")
    watchlist_scan.add_argument(
        "--timeframe", choices=[item.value for item in Timeframe], default="5m"
    )
    watchlist_scan.add_argument("--days", type=int, default=5)
    watchlist_scan.add_argument("--interval-seconds", type=int, default=60)
    watchlist_scan.add_argument("--once", action="store_true")

    backup = subparsers.add_parser("backup")
    backup.add_argument("--output", default="backups/market_sentinel.sqlite3")

    scan = subparsers.add_parser("scan")
    scan.add_argument("--symbol", default="SPY")
    scan.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    scan.add_argument("--days", type=int, default=5)

    serve = subparsers.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    schedule = subparsers.add_parser("schedule")
    schedule.add_argument("--symbols", default="SPY")
    schedule.add_argument("--timeframe", choices=[item.value for item in Timeframe], default="5m")
    schedule.add_argument("--days", type=int, default=5)
    schedule.add_argument("--interval-seconds", type=int, default=60)
    schedule.add_argument("--once", action="store_true")

    args = parser.parse_args()
    command = args.command or "status"
    settings = Settings.from_env()
    if command == "status":
        _print_status(settings)
        return
    if command == "demo-ingest":
        _demo_ingest(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "ingest":
        _provider_ingest(
            settings,
            args.symbol,
            Timeframe(args.timeframe),
            args.days,
            args.provider,
        )
        return
    if command == "ingestion-runs":
        _list_ingestion_runs(settings, args.limit)
        return
    if command == "list-candles":
        _list_candles(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "backtest-demo":
        _backtest_demo(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "walk-forward-demo":
        _walk_forward_demo(
            settings,
            args.symbol,
            Timeframe(args.timeframe),
            args.days,
            args.train_size,
            args.test_size,
            args.model,
        )
        return
    if command == "boosting-demo":
        _boosting_demo(
            args.backend,
            args.symbol,
            Timeframe(args.timeframe),
            args.days,
            args.output,
        )
        return
    if command == "signals-demo":
        _signals_demo(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "dashboard-demo":
        _dashboard_demo(settings, args.symbol, Timeframe(args.timeframe), args.days, args.output)
        return
    if command == "ensemble-demo":
        _ensemble_demo(args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "order-book-demo":
        _order_book_demo(settings, args.provider, args.symbol, args.depth)
        return
    if command == "astra-context-demo":
        _astra_context_demo(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "news-demo":
        _news_demo(args.provider, args.symbol, args.limit, tuple(args.feed_url))
        return
    if command == "paper-demo":
        _paper_demo(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "drift-demo":
        _drift_demo(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "health":
        _health(settings)
        return
    if command == "security-check":
        _security_check()
        return
    if command == "instruments":
        _instruments(args.query, args.asset_class, args.limit)
        return
    if command == "watchlist":
        _watchlist(settings, args.add, args.remove)
        return
    if command == "watchlist-scan":
        _watchlist_scan(
            settings, Timeframe(args.timeframe), args.days, args.interval_seconds, args.once
        )
        return
    if command == "backup":
        _backup(settings, args.output)
        return
    if command == "scan":
        _scan(settings, args.symbol, Timeframe(args.timeframe), args.days)
        return
    if command == "serve":
        _serve(settings, args.host, args.port)
        return
    if command == "schedule":
        _schedule(
            settings,
            tuple(symbol.strip() for symbol in args.symbols.split(",") if symbol.strip()),
            Timeframe(args.timeframe),
            args.days,
            args.interval_seconds,
            args.once,
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
        "completion_releases": [release.code for release in COMPLETION_PLAN],
        "follow_on_releases": [release.code for release in FOLLOW_ON_PLAN],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def _demo_ingest(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    _provider_ingest(settings, symbol, timeframe, days, "demo")


def _provider_ingest(
    settings: Settings,
    symbol: str,
    timeframe: Timeframe,
    days: int,
    provider_name: str | None,
) -> None:
    if days <= 0:
        raise ValueError("days must be positive")
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    market_data_settings = settings.market_data
    if provider_name is not None:
        market_data_settings = replace(market_data_settings, provider=provider_name)
    provider = build_market_data_provider(market_data_settings)
    result = MarketDataIngestionService(provider, repository).ingest(
        symbol, timeframe, start, end
    )
    print(
        json.dumps(
            {
                "run_id": result.run.run_id,
                "provider": result.run.provider,
                "symbol": result.run.symbol,
                "timeframe": result.run.timeframe,
                "fetched_rows": result.run.fetched_rows,
                "stored_rows": result.run.stored_rows,
                "quality": asdict(result.quality),
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
        spread_bps=settings.risk.default_spread_bps,
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
                "spread_bps": settings.risk.default_spread_bps,
                "gross_pnl_bps": report.gross_pnl_bps,
                "net_pnl_bps": report.net_pnl_bps,
                "net_pnl": report.net_pnl,
                "ending_equity": report.ending_equity,
                "total_return_pct": report.total_return_pct,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _walk_forward_demo(
    settings: Settings,
    symbol: str,
    timeframe: Timeframe,
    days: int,
    train_size: int,
    test_size: int,
    model_backend: str,
) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    provider = DemoMarketDataProvider()
    feature_engine = OHLCVFeatureEngine(rolling_window=20)
    candles = list(provider.historical_candles(symbol, timeframe, start, end))
    examples = build_directional_examples(candles, feature_engine, horizon_candles=1)
    evaluator = WalkForwardEvaluator(
        model_factory=lambda: _make_supervised_model(model_backend),
        splitter=WalkForwardSplit(train_size=train_size, test_size=test_size, purge_size=1),
        fee_bps=settings.risk.default_fee_bps,
        slippage_bps=settings.risk.default_slippage_bps,
        spread_bps=settings.risk.default_spread_bps,
    )
    report = evaluator.evaluate(examples)
    print(
        json.dumps(
            {
                "folds": len(report.folds),
                "average_accuracy": report.average_accuracy,
                "average_precision": report.average_precision,
                "average_recall": report.average_recall,
                "average_coverage": report.average_coverage,
                "average_net_pnl_bps": report.average_net_pnl_bps,
                "average_sharpe": report.average_sharpe,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _make_supervised_model(backend: str):
    if backend == "xgboost":
        return XGBoostDirectionalModel(n_estimators=30, max_depth=3)
    if backend == "lightgbm":
        return LightGBMDirectionalModel(n_estimators=30, max_depth=3)
    return LogisticDirectionalModel(horizon_minutes=5, epochs=100)


def _boosting_demo(
    backend: str,
    symbol: str,
    timeframe: Timeframe,
    days: int,
    output: str,
) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    candles = list(DemoMarketDataProvider().historical_candles(symbol, timeframe, start, end))
    feature_engine = OHLCVFeatureEngine(rolling_window=20)
    examples = build_directional_examples(candles, feature_engine, horizon_candles=1)
    model = _make_supervised_model(backend)
    model.fit(examples)
    manifest = model.save(output)
    prediction = model.predict(feature_engine.transform(candles)[-1:])
    print(
        json.dumps(
            {
                "backend": backend,
                "examples": len(examples),
                "manifest": str(manifest),
                "model": model.name,
                "direction": prediction.direction.value,
                "probability": prediction.probability,
                "probability_long": prediction.metadata["probability_long"],
            },
            indent=2,
            sort_keys=True,
        )
    )


def _list_ingestion_runs(settings: Settings, limit: int) -> None:
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    runs = repository.list_ingestion_runs(limit)
    payload = [
        {
            "run_id": run.run_id,
            "provider": run.provider,
            "symbol": run.symbol,
            "timeframe": run.timeframe,
            "status": run.status,
            "fetched_rows": run.fetched_rows,
            "stored_rows": run.stored_rows,
            "finished_at": run.finished_at.isoformat(),
            "quality": json.loads(run.quality_json),
            "error": run.error,
        }
        for run in runs
    ]
    print(json.dumps(payload, indent=2, sort_keys=True))


def _scan(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    result = MarketScanService(settings).scan(symbol, timeframe, days)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))


def _serve(settings: Settings, host: str, port: int) -> None:
    import uvicorn

    from market_sentinel_ai.api import create_app

    uvicorn.run(create_app(settings), host=host, port=port)


def _schedule(
    settings: Settings,
    symbols: tuple[str, ...],
    timeframe: Timeframe,
    days: int,
    interval_seconds: int,
    once: bool,
) -> None:
    scheduler = MarketScheduler(MarketScanService(settings), interval_seconds=interval_seconds)
    if once:
        payload = scheduler.run_once(symbols, timeframe, days).to_dict()
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    scheduler.run_forever(symbols, timeframe, days)


def _signals_demo(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    signal = _demo_signal(settings, symbol, timeframe, days)
    alert_channel = DryRunAlertChannel()
    alert_id = alert_channel.send(signal)
    print(
        json.dumps(
            {
                "alert_id": alert_id,
                "symbol": signal.prediction.symbol,
                "direction": signal.prediction.direction.value,
                "confidence": signal.confidence,
                "probability": signal.prediction.probability,
                "rationale": signal.rationale,
                "risk_notes": list(signal.risk_notes),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _dashboard_demo(
    settings: Settings,
    symbol: str,
    timeframe: Timeframe,
    days: int,
    output: str,
) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    provider = DemoMarketDataProvider()
    feature_engine = OHLCVFeatureEngine(rolling_window=20)
    candles = list(provider.historical_candles(symbol, timeframe, start, end))
    signal = _demo_signal(settings, symbol, timeframe, min(days, 10))

    backtest = SimpleBacktestEngine(
        feature_engine=feature_engine,
        model=MomentumBaselineModel(horizon_minutes=5),
        fee_bps=settings.risk.default_fee_bps,
        slippage_bps=settings.risk.default_slippage_bps,
        spread_bps=settings.risk.default_spread_bps,
    ).run(candles)

    examples = build_directional_examples(candles, feature_engine, horizon_candles=1)
    train_size = min(500, max(20, len(examples) // 3))
    test_size = min(100, max(10, len(examples) // 10))
    walk_forward_report = WalkForwardEvaluator(
        model_factory=lambda: LogisticDirectionalModel(horizon_minutes=5, epochs=50),
        splitter=WalkForwardSplit(train_size=train_size, test_size=test_size, purge_size=1),
        fee_bps=settings.risk.default_fee_bps,
        slippage_bps=settings.risk.default_slippage_bps,
        spread_bps=settings.risk.default_spread_bps,
    ).evaluate(examples)

    html = render_dashboard(
        DashboardViewModel(
            title="Market Sentinel AI",
            generated_at_iso=datetime.now(tz=UTC).isoformat(),
            signals=(signal,),
            backtest=backtest,
            walk_forward={
                "average_accuracy": walk_forward_report.average_accuracy,
                "average_coverage": walk_forward_report.average_coverage,
                "folds": len(walk_forward_report.folds),
            },
        )
    )
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(json.dumps({"dashboard": str(output_path), "bytes": len(html)}, indent=2, sort_keys=True))


def _demo_signal(settings: Settings, symbol: str, timeframe: Timeframe, days: int):
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    provider = DemoMarketDataProvider()
    feature_engine = OHLCVFeatureEngine(rolling_window=20)
    candles = list(provider.historical_candles(symbol, timeframe, start, end))
    features = feature_engine.transform(candles)
    prediction = MomentumBaselineModel(
        horizon_minutes=5, momentum_threshold_bps=0.5
    ).predict(features)
    return SignalEngine(
        min_probability=0.52,
        min_expected_return_bps=(
            settings.risk.default_fee_bps * 2
            + settings.risk.default_slippage_bps * 2
            + settings.risk.default_spread_bps
        ),
    ).from_prediction(prediction)


def _ensemble_demo(symbol: str, timeframe: Timeframe, days: int) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    provider = DemoMarketDataProvider()
    candles = list(provider.historical_candles(symbol, timeframe, start, end))
    feature_engine = OHLCVFeatureEngine(rolling_window=20)
    features = AlignedMultiTimeframeFeatureEngine().transform(candles)
    examples = build_directional_examples(candles, feature_engine, horizon_candles=1)

    logistic = LogisticDirectionalModel(horizon_minutes=5, epochs=75)
    logistic.fit(examples[:-1])
    ensemble = RegimeAwareEnsembleModel(
        models_by_regime={
            Regime.LOW_VOLATILITY: (WeightedModel(logistic, 0.8),),
            Regime.NORMAL: (
                WeightedModel(
                    MomentumBaselineModel(horizon_minutes=5, momentum_threshold_bps=0.5),
                    0.4,
                ),
                WeightedModel(logistic, 0.6),
            ),
            Regime.HIGH_VOLATILITY: (
                WeightedModel(
                    MomentumBaselineModel(horizon_minutes=5, momentum_threshold_bps=1.5),
                    0.7,
                ),
                WeightedModel(logistic, 0.3),
            ),
        },
        horizon_minutes=5,
    )
    prediction = ensemble.predict(features)
    regime = prediction.metadata["regime"]
    higher_timeframe = aggregate_candles(candles, Timeframe.FIFTEEN_MINUTES)
    order_flow_rows = OrderFlowFeatureEngine().transform(
        list(DemoOrderBookProvider().snapshots_from_candles(candles[-5:]))
    )
    print(
        json.dumps(
            {
                "symbol": prediction.symbol,
                "direction": prediction.direction.value,
                "probability": prediction.probability,
                "model": prediction.model_name,
                "regime": regime,
                "source_candles": len(candles),
                "fifteen_minute_candles": len(higher_timeframe),
                "aligned_feature_count": len(features),
                "latest_order_flow": order_flow_rows[-1].values if order_flow_rows else {},
            },
            indent=2,
            sort_keys=True,
        )
    )


def _order_book_demo(
    settings: Settings,
    provider_name: str | None,
    symbol: str,
    depth: int,
) -> None:
    order_book_settings = settings.order_book
    if provider_name is not None:
        order_book_settings = replace(order_book_settings, provider=provider_name)
    provider = build_order_book_provider(order_book_settings)
    snapshot = provider.snapshot(symbol, depth)
    features = OrderFlowFeatureEngine().transform([snapshot])[-1]
    print(
        json.dumps(
            {
                "provider": provider.provider_name,
                "symbol": snapshot.symbol,
                "captured_at": snapshot.captured_at.isoformat(),
                "depth": len(snapshot.bids),
                "best_bid": snapshot.best_bid,
                "best_ask": snapshot.best_ask,
                "spread_bps": snapshot.spread_bps,
                "order_flow_features": features.values,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _astra_context_demo(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    signal = _demo_signal(settings, symbol, timeframe, days)
    news_provider = StaticNewsProvider(
        (
            NewsItem(
                title=f"{symbol.upper()} demo context",
                source="demo-news",
                published_at=datetime.now(tz=UTC),
                summary="Deterministic context item for local Astra gating tests.",
            ),
        )
    )
    gateway = ReasoningGateway(
        provider=AstraReasoningProvider(
            settings.openai,
            ReasoningCache("logs/astra-cache.json"),
        ),
        policy=AstraCostPolicy(
            min_confidence=settings.openai.min_signal_confidence,
            max_requests_per_day=settings.openai.max_context_requests_per_day,
            max_input_tokens_per_request=settings.openai.max_input_tokens_per_request,
            max_output_tokens_per_request=settings.openai.max_output_tokens_per_request,
            max_daily_cost_usd=settings.openai.max_daily_cost_usd,
            input_cost_per_million=settings.openai.input_cost_per_million,
            output_cost_per_million=settings.openai.output_cost_per_million,
        ),
        usage_ledger=AstraUsageLedger(settings.openai.usage_path),
    )
    context = NewsContextBuilder(news_provider).for_symbol(symbol)
    context["sources"] = ["demo-market-data", "demo-order-flow", *context["sources"]]
    reasoning = gateway.maybe_explain(signal, context)
    print(
        json.dumps(
            {
                "signal_direction": signal.prediction.direction.value,
                "signal_confidence": signal.confidence,
                "astra_requested": reasoning is not None,
                "astra_enabled": settings.openai.enabled,
                "thesis": reasoning.thesis if reasoning else None,
                "invalidation": reasoning.invalidation if reasoning else None,
                "risk_notes": list(reasoning.risk_notes) if reasoning else [],
                "context_sources": list(reasoning.context_sources) if reasoning else [],
            },
            indent=2,
            sort_keys=True,
        )
    )


def _news_demo(provider_name: str, symbol: str, limit: int, feed_urls: tuple[str, ...]) -> None:
    if provider_name == "demo":
        provider = StaticNewsProvider(
            (
                NewsItem(
                    title=f"{symbol.upper()} demo news",
                    source="demo-news",
                    published_at=datetime.now(tz=UTC),
                    summary="Deterministic news context for local development.",
                ),
            )
        )
    else:
        if not feed_urls:
            raise ValueError("--feed-url is required when --provider rss")
        from market_sentinel_ai.context import RssNewsProvider

        provider = RssNewsProvider(feed_urls)
    print(
        json.dumps(
            NewsContextBuilder(provider).for_symbol(symbol, limit),
            indent=2,
            sort_keys=True,
        )
    )


def _paper_demo(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    provider = DemoMarketDataProvider()
    candles = list(provider.historical_candles(symbol, timeframe, start, end))
    signal = _demo_signal(settings, symbol, timeframe, days)
    if not signal.is_actionable and len(candles) >= 2:
        prediction = MomentumBaselineModel(horizon_minutes=5, momentum_threshold_bps=0.0).predict(
            OHLCVFeatureEngine(rolling_window=20).transform(candles)
        )
        signal = SignalEngine(min_probability=0.5, min_expected_return_bps=0.0).from_prediction(
            prediction
        )
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    ledger = PaperTradingLedger(
        starting_equity=100_000,
        store=repository,
        account_id="default",
    )
    risk = RiskLimits(
        max_position_pct=settings.risk.max_position_pct,
        max_daily_loss_pct=settings.risk.max_daily_loss_pct,
        fee_bps=settings.risk.default_fee_bps,
        slippage_bps=settings.risk.default_slippage_bps,
        spread_bps=settings.risk.default_spread_bps,
    )
    trade = ledger.simulate_round_trip(
        signal=signal,
        entry_price=candles[-2].open,
        exit_price=candles[-1].close,
        opened_at=candles[-2].opened_at,
        closed_at=candles[-1].opened_at,
        risk=risk,
    )
    JsonlEventLogger("logs/paper-demo.jsonl").log(
        "paper_demo",
        {
            "symbol": symbol.upper(),
            "trade_created": trade is not None,
            "equity": ledger.equity,
        },
    )
    print(
        json.dumps(
            {
                "mode": "paper",
                "real_orders": False,
                "account_id": "default",
                "symbol": symbol.upper(),
                "trade_created": trade is not None,
                "equity": ledger.equity,
                "total_pnl": ledger.total_pnl,
                "trade_pnl": trade.pnl if trade else None,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _drift_demo(settings: Settings, symbol: str, timeframe: Timeframe, days: int) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    candles = list(DemoMarketDataProvider().historical_candles(symbol, timeframe, start, end))
    features = OHLCVFeatureEngine(rolling_window=20).transform(candles)
    midpoint = len(features) // 2
    report = FeatureDriftDetector(threshold=2.5).compare(features[:midpoint], features[midpoint:])
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    report_id = repository.record_drift_report(symbol, "feature-drift-demo", report)
    print(
        json.dumps(
            {
                "symbol": symbol.upper(),
                "drifted": report.drifted,
                "threshold": report.threshold,
                "scores": report.scores,
                "report_id": report_id,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _health(settings: Settings) -> None:
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    print(json.dumps(HealthService(repository).check().to_dict(), indent=2, sort_keys=True))


def _security_check() -> None:
    report = run_security_checks(Path.cwd())
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    if report.status != "ok":
        raise SystemExit(1)


def _instruments(query: str, asset_class: str | None, limit: int) -> None:
    selected = AssetClass(asset_class) if asset_class else None
    print(
        json.dumps(
            [item.to_dict() for item in search_instruments(query, selected, limit)], indent=2
        )
    )


def _watchlist(settings: Settings, add: str | None, remove: str | None) -> None:
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    if add:
        instrument = find_instrument(add) or custom_instrument(add)
        repository.add_watchlist_item(instrument)
    if remove:
        repository.remove_watchlist_item(custom_instrument(remove).symbol)
    print(json.dumps([item.to_dict() for item in repository.list_watchlist()], indent=2))


def _watchlist_scan(
    settings: Settings,
    timeframe: Timeframe,
    days: int,
    interval_seconds: int,
    once: bool,
) -> None:
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    symbols = tuple(item.market_symbol for item in repository.list_watchlist())
    if not symbols:
        raise ValueError("watchlist is empty")
    scheduler = MarketScheduler(
        MarketScanService(settings, repository=repository), interval_seconds
    )
    if once:
        print(
            json.dumps(
                scheduler.run_once(symbols, timeframe, days).to_dict(), indent=2, default=str
            )
        )
        return
    scheduler.run_forever(symbols, timeframe, days)


def _backup(settings: Settings, output: str) -> None:
    repository = SQLiteCandleRepository(sqlite_path_from_url(settings.database_url))
    backup_path = repository.backup_to(output)
    print(json.dumps({"backup": str(backup_path), "real_orders": False}, indent=2, sort_keys=True))
