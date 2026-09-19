from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from market_sentinel_ai.adapters.market_data import (
    MarketDataProviderError,
    build_instrument_search_provider,
)
from market_sentinel_ai.analytics import (
    build_market_chart_payload,
    calculate_risk_metrics,
    chart_window_spec,
)
from market_sentinel_ai.config import Settings
from market_sentinel_ai.dashboard import render_operational_dashboard
from market_sentinel_ai.domain.instruments import (
    AssetClass,
    Instrument,
    custom_instrument,
    find_instrument,
    search_instruments,
)
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.features import OHLCVFeatureEngine
from market_sentinel_ai.models import MomentumBaselineModel
from market_sentinel_ai.monitoring import HealthService
from market_sentinel_ai.operations import MarketScanService, MarketScheduler
from market_sentinel_ai.reasoning import AstraUsageLedger
from market_sentinel_ai.releases import CURRENT_RELEASE
from market_sentinel_ai.signals import SignalEngine, build_trade_plan
from market_sentinel_ai.storage import SQLiteCandleRepository


class ScanRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    timeframe: str = "5m"
    days: int = Field(default=5, gt=0, le=3650)


class WatchlistRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    name: str | None = Field(default=None, max_length=120)
    asset_class: str | None = None
    exchange: str | None = Field(default=None, max_length=60)
    currency: str | None = Field(default=None, max_length=12)
    provider_symbol: str | None = Field(default=None, max_length=24)


class WatchlistScanRequest(BaseModel):
    timeframe: str = "5m"
    days: int = Field(default=5, gt=0, le=3650)


def create_app(
    settings: Settings | None = None,
    service: MarketScanService | None = None,
) -> FastAPI:
    active_settings = settings or Settings.from_env()
    active_service = service or MarketScanService(active_settings)
    repository: SQLiteCandleRepository = active_service.repository
    app = FastAPI(
        title="Market Sentinel AI",
        version=CURRENT_RELEASE.version,
        description="Alert-only quantitative market analysis API.",
    )
    app.state.scan_service = active_service
    app.state.repository = repository

    @app.get("/health")
    def health() -> dict[str, object]:
        report = HealthService(repository).check()
        return {
            **report.to_dict(),
            "environment": active_settings.environment,
            "release": CURRENT_RELEASE.code,
            "version": CURRENT_RELEASE.version,
        }

    @app.get("/api/v1/status")
    def status() -> dict[str, object]:
        return {
            "app": "Market Sentinel AI",
            "release": CURRENT_RELEASE.code,
            "version": CURRENT_RELEASE.version,
            "environment": active_settings.environment,
            "provider": active_settings.market_data.provider,
            "alert_dry_run": active_settings.alerts.dry_run,
            "real_orders_enabled": False,
        }

    @app.get("/api/v1/signals")
    def signals(
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
    ) -> list[dict[str, object]]:
        return [
            signal.to_dict()
            for signal in repository.list_signals(symbol=symbol, timeframe=timeframe, limit=limit)
        ]

    @app.get("/api/v1/alerts")
    def alerts(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, object]]:
        return [alert.to_dict() for alert in repository.list_alerts(limit)]

    @app.get("/api/v1/runs")
    def runs(limit: int = Query(default=20, ge=1, le=200)) -> list[dict[str, object]]:
        return [run.to_dict() for run in repository.list_scheduler_runs(limit)]

    @app.get("/api/v1/operations/summary")
    def operations_summary() -> dict[str, object]:
        runs = repository.list_scheduler_runs(limit=1)
        health = repository.list_health_checks(limit=1)
        return {
            "release": CURRENT_RELEASE.code,
            "version": CURRENT_RELEASE.version,
            "watchlist_count": len(repository.list_watchlist()),
            "signal_count": len(repository.list_signals(limit=500)),
            "alert_count": len(repository.list_alerts(limit=500)),
            "last_scheduler_run": runs[0].to_dict() if runs else None,
            "last_health_check": health[0] if health else None,
            "alert_dedupe_minutes": active_settings.alerts.dedupe_minutes,
            "real_orders_enabled": False,
        }

    @app.get("/api/v1/instruments")
    def instruments(
        q: str = "",
        asset_class: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        source: str = "local",
    ) -> list[dict[str, object]]:
        try:
            selected_class = AssetClass(asset_class) if asset_class else None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="unsupported asset class") from exc
        local = search_instruments(q, selected_class, limit)
        if source not in {"local", "provider", "auto"}:
            raise HTTPException(status_code=422, detail="unsupported instrument search source")
        if source == "local" or not q.strip():
            return [item.to_dict() for item in local]
        try:
            provider = build_instrument_search_provider(active_settings.instrument_search)
            remote = provider.search(q, limit)
        except (MarketDataProviderError, ValueError) as exc:
            if source == "provider":
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            remote = []
        if source == "provider":
            return [item.to_dict() for item in remote]
        merged = {item.symbol: item for item in local}
        merged.update({item.symbol: item for item in remote})
        return [item.to_dict() for item in list(merged.values())[:limit]]

    @app.get("/api/v1/watchlist")
    def watchlist() -> list[dict[str, object]]:
        return [item.to_dict() for item in repository.list_watchlist()]

    @app.get("/api/v1/market/{symbol:path}")
    def market_chart(symbol: str, window: str = "1d") -> dict[str, object]:
        try:
            normalized = custom_instrument(symbol).symbol
            spec = chart_window_spec(window)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        selected = next(
            (item for item in repository.list_watchlist() if item.symbol == normalized),
            None,
        )
        selected = selected or find_instrument(normalized) or custom_instrument(normalized)
        market_symbol = selected.market_symbol
        end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        start = end - (spec.lookback or timedelta(days=3650))
        candles = []
        source = "cache"

        try:
            fetched = list(
                active_service.provider.historical_candles(
                    market_symbol,
                    spec.timeframe,
                    start,
                    end,
                )
            )
            candles = sorted(
                [
                    candle
                    for candle in fetched
                    if start <= candle.opened_at < end
                ],
                key=lambda candle: candle.opened_at,
            )
            if candles:
                repository.upsert_many(candles)
                source = "provider"
        except (MarketDataProviderError, OSError, ValueError):
            candles = []

        if not candles:
            cached = repository.list_candles(market_symbol, spec.timeframe, start, end)
            provider_name = getattr(active_service.provider, "provider_name", "unknown")
            if provider_name != "demo":
                latest_run = repository.latest_ingestion_run(market_symbol, spec.timeframe)
                if latest_run is None or latest_run.provider != provider_name:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            f"fresh {provider_name} market data is unavailable for {normalized}; "
                            "the UI will not substitute demo or another provider's cached data"
                        ),
                    )
            candles = cached
        if not candles and market_symbol != normalized:
            candles = repository.list_candles(normalized, spec.timeframe, start, end)
        if not candles:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"no market candles available for {normalized} in {spec.label}; "
                    "check the provider or run an ingestion scan"
                ),
            )

        features = OHLCVFeatureEngine().transform(candles)
        horizon_minutes = {
            Timeframe.ONE_MINUTE: 1,
            Timeframe.FIVE_MINUTES: 5,
            Timeframe.FIFTEEN_MINUTES: 15,
            Timeframe.ONE_HOUR: 60,
            Timeframe.ONE_DAY: 1440,
        }[spec.timeframe]
        prediction = MomentumBaselineModel(horizon_minutes=horizon_minutes).predict(features)
        round_trip_cost_bps = (
            active_settings.risk.default_fee_bps * 2
            + active_settings.risk.default_slippage_bps * 2
            + active_settings.risk.default_spread_bps
        )
        signal = SignalEngine(
            min_probability=0.55,
            min_expected_return_bps=round_trip_cost_bps,
        ).from_prediction(prediction)
        plan = build_trade_plan(
            signal,
            candles[-1],
            features[-1],
            spec.timeframe,
            round_trip_cost_bps,
        )
        return build_market_chart_payload(
            candles,
            signal,
            plan,
            features[-1],
            instrument=selected.to_dict(),
            spec=spec,
            provider=getattr(active_service.provider, "provider_name", "unknown"),
            source=source,
        )

    @app.post("/api/v1/watchlist")
    def add_watchlist_item(request: WatchlistRequest) -> dict[str, object]:
        try:
            known = find_instrument(request.symbol)
            if known and not any(
                value is not None
                for value in (
                    request.name,
                    request.asset_class,
                    request.exchange,
                    request.currency,
                    request.provider_symbol,
                )
            ):
                instrument = known
            else:
                instrument = Instrument(
                    symbol=request.symbol,
                    name=request.name or (known.name if known else request.symbol.upper()),
                    asset_class=AssetClass(
                        request.asset_class or (known.asset_class if known else "equity")
                    ),
                    exchange=request.exchange or (known.exchange if known else "unknown"),
                    currency=request.currency or (known.currency if known else "USD"),
                    provider_symbol=request.provider_symbol
                    or (known.market_symbol if known else None),
                    featured=known.featured if known else False,
                )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return repository.add_watchlist_item(instrument).to_dict()

    @app.delete("/api/v1/watchlist/{symbol}")
    def remove_watchlist_item(symbol: str) -> dict[str, object]:
        try:
            normalized = custom_instrument(symbol).symbol
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not repository.remove_watchlist_item(normalized):
            raise HTTPException(status_code=404, detail="instrument not in watchlist")
        return {"symbol": normalized, "removed": True}

    @app.post("/api/v1/watchlist/scan")
    def scan_watchlist(request: WatchlistScanRequest) -> dict[str, object]:
        try:
            timeframe = Timeframe(request.timeframe)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="unsupported timeframe") from exc
        symbols = tuple(item.market_symbol for item in repository.list_watchlist())
        if not symbols:
            raise HTTPException(status_code=422, detail="watchlist is empty")
        result = MarketScheduler(active_service).run_once(symbols, timeframe, request.days)
        return result.to_dict()

    @app.get("/api/v1/astra-usage")
    def astra_usage() -> dict[str, object]:
        snapshot = AstraUsageLedger(active_settings.openai.usage_path).snapshot()
        return {
            "day": snapshot.day.isoformat(),
            "requests": snapshot.requests,
            "cache_hits": snapshot.cache_hits,
            "input_tokens_estimate": snapshot.input_tokens_estimate,
            "output_tokens_estimate": snapshot.output_tokens_estimate,
            "estimated_cost_usd": snapshot.estimated_cost_usd,
            "max_requests_per_day": active_settings.openai.max_context_requests_per_day,
            "max_daily_cost_usd": active_settings.openai.max_daily_cost_usd,
        }

    @app.get("/api/v1/health/details")
    def health_details() -> dict[str, object]:
        return HealthService(repository).check().to_dict()

    @app.get("/api/v1/paper/account")
    def paper_account(account_id: str = "default") -> dict[str, object]:
        snapshot = repository.load_paper_account(account_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="paper account not found")
        return {
            "account_id": snapshot.account_id,
            "starting_equity": snapshot.starting_equity,
            "equity": snapshot.equity,
            "updated_at": snapshot.updated_at.isoformat(),
            "real_execution_enabled": snapshot.real_execution_enabled,
        }

    @app.get("/api/v1/paper/trades")
    def paper_trades(
        account_id: str = "default",
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> list[dict[str, object]]:
        return [
            {
                "trade_id": record.trade_id,
                "account_id": record.account_id,
                "symbol": record.trade.symbol,
                "direction": record.trade.direction.value,
                "quantity": record.trade.quantity,
                "entry_price": record.trade.entry_price,
                "exit_price": record.trade.exit_price,
                "pnl": record.trade.pnl,
                "opened_at": record.trade.opened_at.isoformat(),
                "closed_at": record.trade.closed_at.isoformat(),
            }
            for record in repository.list_paper_trades(account_id, limit)
        ]

    @app.get("/api/v1/paper/metrics")
    def paper_metrics(
        account_id: str = "default",
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> dict[str, object]:
        snapshot = repository.load_paper_account(account_id)
        starting_equity = snapshot.starting_equity if snapshot else 100_000.0
        records = repository.list_paper_trades(account_id, limit)
        metrics = calculate_risk_metrics(
            [record.trade for record in records],
            repository.list_signals(limit=limit),
            starting_equity=starting_equity,
            max_position_pct=active_settings.risk.max_position_pct,
        )
        return {"account_id": account_id, **metrics.to_dict()}

    @app.get("/api/v1/drift")
    def drift_reports(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, object]]:
        return repository.list_drift_reports(limit)

    @app.get("/api/v1/health/history")
    def health_history(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, object]]:
        return repository.list_health_checks(limit)

    @app.post("/api/v1/scan")
    def scan(request: ScanRequest) -> dict[str, object]:
        try:
            timeframe = Timeframe(request.timeframe)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="unsupported timeframe") from exc
        result = active_service.scan(request.symbol, timeframe, request.days)
        return result.to_dict()

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        snapshot = repository.load_paper_account("default")
        metrics = calculate_risk_metrics(
            [record.trade for record in repository.list_paper_trades("default")],
            repository.list_signals(limit=500),
            starting_equity=snapshot.starting_equity if snapshot else 100_000.0,
            max_position_pct=active_settings.risk.max_position_pct,
        ).to_dict()
        return render_operational_dashboard(
            repository.list_signals(limit=50),
            repository.list_alerts(limit=50),
            generated_at_iso=datetime.now(tz=UTC).isoformat(),
            environment=active_settings.environment,
            watchlist=repository.list_watchlist(),
            risk_metrics=metrics,
        )

    return app
