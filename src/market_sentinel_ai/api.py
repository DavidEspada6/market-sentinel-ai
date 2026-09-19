from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from market_sentinel_ai.config import Settings
from market_sentinel_ai.dashboard import render_operational_dashboard
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.monitoring import HealthService
from market_sentinel_ai.operations import MarketScanService
from market_sentinel_ai.reasoning import AstraUsageLedger
from market_sentinel_ai.releases import CURRENT_RELEASE
from market_sentinel_ai.storage import SQLiteCandleRepository


class ScanRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
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
        return render_operational_dashboard(
            repository.list_signals(limit=50),
            repository.list_alerts(limit=50),
            generated_at_iso=datetime.now(tz=UTC).isoformat(),
            environment=active_settings.environment,
        )

    return app
