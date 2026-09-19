from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from market_sentinel_ai.config import Settings
from market_sentinel_ai.dashboard import render_operational_dashboard
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.operations import MarketScanService
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
        return {
            "status": "ok",
            "environment": active_settings.environment,
            "release": CURRENT_RELEASE.code,
            "version": CURRENT_RELEASE.version,
            "real_orders_enabled": False,
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
