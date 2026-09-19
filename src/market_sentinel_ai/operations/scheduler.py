from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event
from typing import TYPE_CHECKING
from uuid import uuid4

from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.domain.operations import SchedulerRunRecord

if TYPE_CHECKING:
    from market_sentinel_ai.operations.service import MarketScanService, ScanResult


@dataclass(frozen=True)
class SchedulerRunResult:
    run: SchedulerRunRecord
    scans: tuple[ScanResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "run": self.run.to_dict(),
            "scans": [scan.to_dict() for scan in self.scans],
        }


class MarketScheduler:
    def __init__(self, service: MarketScanService, interval_seconds: int = 60) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.service = service
        self.interval_seconds = interval_seconds

    def run_once(
        self,
        symbols: tuple[str, ...],
        timeframe: Timeframe,
        days: int = 5,
    ) -> SchedulerRunResult:
        if not symbols:
            raise ValueError("symbols cannot be empty")
        started_at = datetime.now(tz=UTC)
        scans: list[ScanResult] = []
        error: str | None = None
        for symbol in symbols:
            try:
                scans.append(self.service.scan(symbol, timeframe, days))
            except Exception as exc:
                error = str(exc)
        alerts = sum(len(scan.alerts) for scan in scans)
        status = "completed" if error is None else ("partial" if scans else "failed")
        run = SchedulerRunRecord(
            run_id=str(uuid4()),
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            status=status,
            symbols=tuple(symbols),
            signal_count=len(scans),
            alert_count=alerts,
            error=error,
        )
        self.service.repository.record_scheduler_run(run)
        return SchedulerRunResult(run=run, scans=tuple(scans))

    def run_forever(
        self,
        symbols: tuple[str, ...],
        timeframe: Timeframe,
        days: int = 5,
        stop_event: Event | None = None,
    ) -> None:
        event = stop_event or Event()
        while not event.is_set():
            self.run_once(symbols, timeframe, days)
            event.wait(self.interval_seconds)
