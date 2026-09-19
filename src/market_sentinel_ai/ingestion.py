from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import uuid4

from market_sentinel_ai.data_quality import (
    CandleQualityReport,
    analyze_candle_sequence,
    validate_candle_sequence,
)
from market_sentinel_ai.domain.ingestion import IngestionRun
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.ports.market_data import MarketDataProvider
from market_sentinel_ai.storage.sqlite import SQLiteCandleRepository


@dataclass(frozen=True)
class IngestionResult:
    run: IngestionRun
    quality: CandleQualityReport


class MarketDataIngestionService:
    def __init__(
        self,
        provider: MarketDataProvider,
        repository: SQLiteCandleRepository,
    ) -> None:
        self.provider = provider
        self.repository = repository

    def ingest(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> IngestionResult:
        run_id = str(uuid4())
        started_at = datetime.now(tz=UTC)
        try:
            candles = list(self.provider.historical_candles(symbol, timeframe, start, end))
            validate_candle_sequence(candles)
            if any(
                candle.symbol != symbol.upper() or candle.timeframe is not timeframe
                for candle in candles
            ):
                raise ValueError("provider returned candles for a different symbol or timeframe")
            quality = analyze_candle_sequence(candles, observed_at=end)
            if not quality.accepted:
                raise ValueError(
                    "market data failed quality gates: expected non-empty, ordered, unique candles"
                )
            stored_rows = self.repository.upsert_many(candles)
            run = self._run(
                run_id=run_id,
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                started_at=started_at,
                status="completed",
                fetched_rows=len(candles),
                stored_rows=stored_rows,
                quality=quality,
            )
            self.repository.record_ingestion_run(run)
            return IngestionResult(run=run, quality=quality)
        except Exception as exc:
            empty_quality = CandleQualityReport(0, 0, 0, 0, None)
            failed = self._run(
                run_id=run_id,
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                started_at=started_at,
                status="failed",
                fetched_rows=0,
                stored_rows=0,
                quality=empty_quality,
                error=str(exc),
            )
            self.repository.record_ingestion_run(failed)
            raise

    def _run(
        self,
        *,
        run_id: str,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        started_at: datetime,
        status: str,
        fetched_rows: int,
        stored_rows: int,
        quality: CandleQualityReport,
        error: str | None = None,
    ) -> IngestionRun:
        return IngestionRun(
            run_id=run_id,
            provider=self.provider.provider_name,
            symbol=symbol.upper(),
            timeframe=timeframe.value,
            requested_start=start,
            requested_end=end,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            status=status,
            fetched_rows=fetched_rows,
            stored_rows=stored_rows,
            quality_json=json.dumps(asdict(quality), sort_keys=True),
            error=error,
        )
