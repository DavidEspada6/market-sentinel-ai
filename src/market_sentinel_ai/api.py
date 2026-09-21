from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event, Thread

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from market_sentinel_ai.adapters.market_data import (
    MarketDataProviderError,
    build_instrument_search_provider,
)
from market_sentinel_ai.analytics import (
    ChartWindowSpec,
    build_market_chart_payload,
    calculate_risk_metrics,
    chart_window_spec,
)
from market_sentinel_ai.config import Settings
from market_sentinel_ai.dashboard import render_operational_dashboard, render_prediction_analytics
from market_sentinel_ai.domain.instruments import (
    AssetClass,
    Instrument,
    custom_instrument,
    find_instrument,
    search_instruments,
)
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.domain.paper import PaperPosition
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.monitoring import HealthService
from market_sentinel_ai.operations import MarketScanService, MarketScheduler, PredictionMonitor
from market_sentinel_ai.paper import SimulationError, SimulationLedger
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


class SimulationResetRequest(BaseModel):
    starting_equity: float = Field(gt=0, le=1_000_000_000)


class SimulationPositionRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    direction: str
    margin: float = Field(gt=0, le=1_000_000_000)
    leverage: float = Field(default=1.0, ge=1.0, le=10.0)
    price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)


class SimulationCloseRequest(BaseModel):
    price: float | None = Field(default=None, gt=0)


def _chart_fallback_lookback(timeframe: Timeframe) -> timedelta:
    return {
        Timeframe.ONE_MINUTE: timedelta(days=7),
        Timeframe.FIVE_MINUTES: timedelta(days=60),
        Timeframe.FIFTEEN_MINUTES: timedelta(days=60),
        Timeframe.ONE_HOUR: timedelta(days=180),
        Timeframe.ONE_DAY: timedelta(days=3650),
    }[timeframe]


def _select_chart_window(
    candles: list,
    spec: ChartWindowSpec,
    used_fallback: bool,
) -> list:
    if not used_fallback or spec.lookback is None or not candles:
        return candles
    latest = candles[-1].opened_at
    window_start = latest - spec.lookback
    selected = [candle for candle in candles if window_start <= candle.opened_at <= latest]
    return selected or [candles[-1]]


def create_app(
    settings: Settings | None = None,
    service: MarketScanService | None = None,
) -> FastAPI:
    active_settings = settings or Settings.from_env()
    active_service = service or MarketScanService(active_settings)
    repository: SQLiteCandleRepository = active_service.repository
    prediction_monitor = PredictionMonitor(active_service)
    monitor_stop = Event()
    monitor_thread: Thread | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal monitor_thread
        monitor_stop.clear()
        monitor_thread = Thread(
            target=prediction_monitor.run_forever,
            args=(monitor_stop,),
            kwargs={"interval_seconds": 30},
            daemon=True,
            name="market-sentinel-predictions",
        )
        monitor_thread.start()
        try:
            yield
        finally:
            monitor_stop.set()
            if monitor_thread is not None:
                monitor_thread.join(timeout=5)

    app = FastAPI(
        title="Market Sentinel AI",
        version=CURRENT_RELEASE.version,
        description="Quantitative market analysis API with local paper simulation only.",
        lifespan=lifespan,
    )
    app.state.scan_service = active_service
    app.state.repository = repository
    app.state.prediction_monitor = prediction_monitor

    def simulation_ledger() -> SimulationLedger:
        return SimulationLedger(
            store=repository,
            account_id="simulation",
            fee_bps=active_settings.risk.default_fee_bps,
            slippage_bps=active_settings.risk.default_slippage_bps,
            spread_bps=active_settings.risk.default_spread_bps,
        )

    def latest_simulation_prices(symbols: set[str]) -> dict[str, float]:
        prices: dict[str, float] = {}
        end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        start = end - timedelta(days=2)
        for symbol in symbols:
            try:
                selected = next(
                    (item for item in repository.list_watchlist() if item.symbol == symbol),
                    None,
                )
                selected = selected or find_instrument(symbol) or custom_instrument(symbol)
                market_symbol = selected.market_symbol
                fetched = list(
                    active_service.provider.historical_candles(
                        market_symbol,
                        Timeframe.FIVE_MINUTES,
                        start,
                        end,
                    )
                )
                candles = sorted(fetched, key=lambda candle: candle.opened_at)
                if candles:
                    repository.upsert_many(candles)
                    prices[symbol] = candles[-1].close
                    continue
                cached = repository.list_candles(
                    market_symbol,
                    Timeframe.FIVE_MINUTES,
                    start,
                    end,
                )
                if cached:
                    prices[symbol] = cached[-1].close
            except (MarketDataProviderError, OSError, ValueError):
                continue
        return prices

    def simulation_price(symbol: str, supplied_price: float | None = None) -> float:
        if supplied_price is not None:
            return supplied_price
        price = latest_simulation_prices({symbol}).get(symbol)
        if price is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"fresh price unavailable for {symbol}; provide a current chart price "
                    "or verify the market-data provider"
                ),
            )
        return price

    def refresh_simulation(ledger: SimulationLedger) -> dict[str, float]:
        prices = latest_simulation_prices({position.symbol for position in ledger.positions})
        ledger.refresh_prices(prices)
        return prices

    def simulation_position_payload(
        ledger: SimulationLedger,
        position: PaperPosition,
    ) -> dict[str, object]:
        return {
            "position_id": position.position_id,
            "symbol": position.symbol,
            "direction": position.direction.value,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "mark_price": position.mark_price,
            "leverage": position.leverage,
            "margin": position.margin,
            "stop_loss": position.stop_loss,
            "take_profit": position.take_profit,
            "notional": position.mark_notional,
            "unrealized_pnl": ledger.position_unrealized_pnl(position),
            "liquidation_price": ledger.liquidation_price(position),
            "opened_at": position.opened_at.isoformat(),
            "updated_at": position.updated_at.isoformat(),
        }

    def simulation_account_payload(
        ledger: SimulationLedger,
        prices: dict[str, float],
    ) -> dict[str, object]:
        return {
            "account_id": ledger.account_id,
            "mode": "simulation",
            "real_execution_enabled": False,
            "real_orders_enabled": False,
            "starting_equity": ledger.starting_equity,
            "cash_balance": ledger.cash,
            "equity": ledger.equity,
            "available_margin": ledger.available_margin,
            "used_margin": ledger.used_margin,
            "unrealized_pnl": ledger.unrealized_pnl,
            "realized_pnl": ledger.realized_pnl,
            "total_pnl": ledger.equity - ledger.starting_equity,
            "return_pct": (ledger.equity / ledger.starting_equity - 1) * 100,
            "exposure": ledger.exposure,
            "max_leverage": ledger.MAX_LEVERAGE,
            "prices_refreshed": sorted(prices),
            "updated_at": datetime.now(tz=UTC).isoformat(),
            "positions": [
                simulation_position_payload(ledger, position) for position in ledger.positions
            ],
        }

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
            "simulation_enabled": True,
            "simulation_max_leverage": SimulationLedger.MAX_LEVERAGE,
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

    @app.get("/api/v1/model-status")
    def model_status() -> list[dict[str, object]]:
        return [dict(item) for item in active_service.model_status()]

    @app.post("/api/v1/predictions/run")
    def run_predictions() -> dict[str, object]:
        return prediction_monitor.run_once().to_dict()

    @app.get("/api/v1/predictions/status")
    def prediction_status() -> dict[str, object]:
        return prediction_monitor.status()

    @app.get("/api/v1/predictions")
    def predictions(
        symbol: str | None = None,
        timeframe: str | None = None,
        window: str | None = None,
        status: str | None = None,
        limit: int = Query(default=500, ge=1, le=10_000),
    ) -> list[dict[str, object]]:
        if status not in {None, "pending", "resolved"}:
            raise HTTPException(status_code=422, detail="status must be pending or resolved")
        return [
            item.to_dict()
            for item in repository.list_predictions(
                symbol=symbol,
                timeframe=timeframe,
                window=window,
                status=status,
                limit=limit,
            )
        ]

    @app.post("/api/v1/predictions/reset")
    def reset_prediction_history() -> dict[str, object]:
        deleted = repository.reset_prediction_history()
        return {"deleted": deleted, "simulation_history_preserved": True}

    @app.get("/api/v1/prediction-analytics")
    def prediction_analytics(
        symbol: str | None = None,
        timeframe: str | None = None,
        window: str | None = None,
        status: str | None = None,
        limit: int = Query(default=5000, ge=1, le=20_000),
    ) -> dict[str, object]:
        if status not in {None, "pending", "resolved"}:
            raise HTTPException(status_code=422, detail="status must be pending or resolved")
        records = repository.list_predictions(
            symbol=symbol,
            timeframe=timeframe,
            window=window,
            status=status,
            limit=limit,
        )
        by_window: dict[str, list] = {}
        by_symbol: dict[str, list] = {}
        for item in records:
            by_window.setdefault(item.window, []).append(item)
            by_symbol.setdefault(item.symbol, []).append(item)

        def aggregate(items: list) -> dict[str, object]:
            scored = [item for item in items if item.status == "resolved"]
            wins = sum(1 for item in scored if item.correct is True)
            returns = [
                item.actual_return_bps
                for item in scored
                if item.actual_return_bps is not None
            ]
            expected = [
                item.expected_return_bps
                for item in items
                if item.expected_return_bps is not None
            ]
            return {
                "total": len(items),
                "pending": len(items) - len(scored),
                "resolved": len(scored),
                "correct": wins,
                "incorrect": len(scored) - wins,
                "accuracy_pct": (wins / len(scored) * 100) if scored else None,
                "avg_actual_return_bps": sum(returns) / len(returns) if returns else None,
                "avg_expected_return_bps": sum(expected) / len(expected) if expected else None,
            }

        def grouped(items_by_key: dict[str, list]) -> list[dict[str, object]]:
            return [
                {"key": key, **aggregate(items)}
                for key, items in sorted(items_by_key.items())
            ]

        horizon_rows = grouped(by_window)
        scored_horizons = [
            item for item in horizon_rows if item["accuracy_pct"] is not None
        ]
        best = (
            max(scored_horizons, key=lambda item: float(item["accuracy_pct"]))
            if scored_horizons
            else None
        )
        return {
            "filters": {
                "symbol": symbol,
                "timeframe": timeframe,
                "window": window,
                "status": status,
                "limit": limit,
            },
            **aggregate(records),
            "best_window": best["key"] if best else None,
            "by_window": horizon_rows,
            "by_symbol": grouped(by_symbol),
            "recent": [item.to_dict() for item in records[:100]],
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
        data_notice: str | None = None

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

        # Short chart windows are often empty outside market hours. Retry with
        # a provider-supported history window so the model can recalculate from
        # the latest completed session instead of returning stale UI state.
        if not candles and spec.lookback is not None:
            fallback_start = end - _chart_fallback_lookback(spec.timeframe)
            try:
                fallback = list(
                    active_service.provider.historical_candles(
                        market_symbol,
                        spec.timeframe,
                        fallback_start,
                        end,
                    )
                )
                candles = sorted(
                    [
                        candle
                        for candle in fallback
                        if fallback_start <= candle.opened_at < end
                    ],
                    key=lambda candle: candle.opened_at,
                )
                if candles:
                    repository.upsert_many(candles)
                    source = "provider"
                    data_notice = (
                        f"No había velas nuevas en {spec.label}; se recalcula con la "
                        f"última vela disponible ({candles[-1].opened_at.isoformat()})."
                    )
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

        chart_candles = _select_chart_window(candles, spec, data_notice is not None)
        analysis_candles = candles
        if len(candles) < 123:
            training_days = {
                Timeframe.ONE_MINUTE: 5,
                Timeframe.FIVE_MINUTES: 5,
                Timeframe.FIFTEEN_MINUTES: 30,
                Timeframe.ONE_HOUR: 30,
                Timeframe.ONE_DAY: 365,
            }[spec.timeframe]
            try:
                training_candles = sorted(
                    list(
                        active_service.provider.historical_candles(
                            market_symbol,
                            spec.timeframe,
                            end - timedelta(days=training_days),
                            end,
                        )
                    ),
                    key=lambda candle: candle.opened_at,
                )
                if (
                    len(training_candles) >= 123
                    and training_candles[-1].opened_at >= candles[-1].opened_at
                ):
                    analysis_candles = training_candles
                    repository.upsert_many(training_candles)
            except (MarketDataProviderError, OSError, ValueError):
                pass

        round_trip_cost_bps = (
            active_settings.risk.default_fee_bps * 2
            + active_settings.risk.default_slippage_bps * 2
            + active_settings.risk.default_spread_bps
        )
        market_context = active_service.market_context(normalized)
        prediction, features = active_service.predict_market(
            analysis_candles,
            spec.timeframe,
            round_trip_cost_bps,
            market_context=market_context,
        )
        signal = SignalEngine(
            min_probability=0.55,
            min_expected_return_bps=round_trip_cost_bps,
        ).from_prediction(prediction)
        plan = build_trade_plan(
            signal,
            analysis_candles[-1],
            features[-1],
            spec.timeframe,
            round_trip_cost_bps,
        )
        return build_market_chart_payload(
            chart_candles,
            signal,
            plan,
            features[-1],
            instrument=selected.to_dict(),
            spec=spec,
            provider=getattr(active_service.provider, "provider_name", "unknown"),
            source=source,
            data_notice=data_notice,
            market_context=market_context,
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
                "margin": record.trade.margin,
                "leverage": record.trade.leverage,
                "entry_cost": record.trade.entry_cost,
                "exit_cost": record.trade.exit_cost,
                "notional": record.trade.notional,
                "close_reason": record.trade.close_reason,
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

    @app.get("/api/v1/simulation/account")
    def simulation_account() -> dict[str, object]:
        ledger = simulation_ledger()
        prices = refresh_simulation(ledger)
        return simulation_account_payload(ledger, prices)

    @app.post("/api/v1/simulation/reset")
    def reset_simulation(request: SimulationResetRequest) -> dict[str, object]:
        ledger = simulation_ledger()
        try:
            ledger.reset(request.starting_equity)
        except SimulationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return simulation_account_payload(ledger, {})

    @app.post("/api/v1/simulation/positions")
    def open_simulation_position(request: SimulationPositionRequest) -> dict[str, object]:
        ledger = simulation_ledger()
        try:
            direction = Direction(request.direction.upper())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="direction must be LONG or SHORT") from exc
        normalized_symbol = request.symbol.strip().upper()
        price = simulation_price(normalized_symbol, request.price)
        try:
            position = ledger.open_position(
                symbol=normalized_symbol,
                direction=direction,
                margin=request.margin,
                leverage=request.leverage,
                entry_price=price,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
            )
        except SimulationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "position": simulation_position_payload(ledger, position),
            "account": simulation_account_payload(ledger, {normalized_symbol: price}),
        }

    @app.post("/api/v1/simulation/positions/{position_id}/close")
    def close_simulation_position(
        position_id: str,
        request: SimulationCloseRequest,
    ) -> dict[str, object]:
        ledger = simulation_ledger()
        position = next(
            (item for item in ledger.positions if item.position_id == position_id),
            None,
        )
        if position is None:
            raise HTTPException(status_code=404, detail="simulation position not found")
        price = simulation_price(position.symbol, request.price)
        try:
            trade = ledger.close_position(position_id, price)
        except SimulationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "trade": {
                "symbol": trade.symbol,
                "direction": trade.direction.value,
                "quantity": trade.quantity,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl": trade.pnl,
                "margin": trade.margin,
                "leverage": trade.leverage,
                "entry_cost": trade.entry_cost,
                "exit_cost": trade.exit_cost,
                "notional": trade.notional,
                "close_reason": trade.close_reason,
                "opened_at": trade.opened_at.isoformat(),
                "closed_at": trade.closed_at.isoformat(),
            },
            "account": simulation_account_payload(ledger, {position.symbol: price}),
        }

    @app.get("/api/v1/simulation/trades")
    def simulation_trades(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> list[dict[str, object]]:
        ledger = simulation_ledger()
        return [
            {
                "trade_id": record.trade_id,
                "symbol": record.trade.symbol,
                "direction": record.trade.direction.value,
                "quantity": record.trade.quantity,
                "entry_price": record.trade.entry_price,
                "exit_price": record.trade.exit_price,
                "pnl": record.trade.pnl,
                "margin": record.trade.margin,
                "leverage": record.trade.leverage,
                "entry_cost": record.trade.entry_cost,
                "exit_cost": record.trade.exit_cost,
                "notional": record.trade.notional,
                "close_reason": record.trade.close_reason,
                "opened_at": record.trade.opened_at.isoformat(),
                "closed_at": record.trade.closed_at.isoformat(),
            }
            for record in repository.list_paper_trades(ledger.account_id, limit)
        ]

    @app.get("/api/v1/simulation/metrics")
    def simulation_metrics(
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> dict[str, object]:
        ledger = simulation_ledger()
        refresh_simulation(ledger)
        metrics = calculate_risk_metrics(
            ledger.trades,
            [],
            starting_equity=ledger.starting_equity,
            max_position_pct=1.0,
        )
        metrics = replace(
            metrics,
            unrealized_pnl=ledger.unrealized_pnl,
            total_pnl=ledger.equity - ledger.starting_equity,
            exposure=ledger.exposure,
            starting_equity=ledger.starting_equity,
            sample_size=min(len(ledger.trades), limit),
        )
        return {
            "account_id": ledger.account_id,
            **metrics.to_dict(),
            "cash_balance": ledger.cash,
            "equity": ledger.equity,
            "available_margin": ledger.available_margin,
            "used_margin": ledger.used_margin,
            "open_positions": len(ledger.positions),
            "max_leverage": ledger.MAX_LEVERAGE,
            "real_orders_enabled": False,
        }

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

    @app.get("/analysis", response_class=HTMLResponse)
    def analysis() -> str:
        return render_prediction_analytics()

    return app
