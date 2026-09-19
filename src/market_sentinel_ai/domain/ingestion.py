from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IngestionRun:
    run_id: str
    provider: str
    symbol: str
    timeframe: str
    requested_start: datetime
    requested_end: datetime
    started_at: datetime
    finished_at: datetime
    status: str
    fetched_rows: int
    stored_rows: int
    quality_json: str
    error: str | None = None
