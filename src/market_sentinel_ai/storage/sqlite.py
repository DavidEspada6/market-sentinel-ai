from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import datetime
from pathlib import Path

from market_sentinel_ai.domain.ingestion import IngestionRun
from market_sentinel_ai.domain.market import Candle, Timeframe

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (symbol, timeframe, opened_at)
);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe_opened_at
ON candles(symbol, timeframe, opened_at);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    requested_start TEXT NOT NULL,
    requested_end TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    fetched_rows INTEGER NOT NULL,
    stored_rows INTEGER NOT NULL,
    quality_json TEXT NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_finished_at
ON ingestion_runs(finished_at DESC);
"""


class SQLiteCandleRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert_many(self, candles: Iterable[Candle]) -> int:
        records = [
            (
                candle.symbol.upper(),
                candle.timeframe.value,
                candle.opened_at.isoformat(),
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
            )
            for candle in candles
        ]
        if not records:
            return 0

        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                    INSERT INTO candles (
                        symbol, timeframe, opened_at, open, high, low, close, volume
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, timeframe, opened_at) DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        volume = excluded.volume
                    """,
                records,
            )
        return len(records)

    def list_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT symbol, timeframe, opened_at, open, high, low, close, volume
                FROM candles
                WHERE symbol = ?
                  AND timeframe = ?
                  AND opened_at >= ?
                  AND opened_at < ?
                ORDER BY opened_at ASC
                """,
                (symbol.upper(), timeframe.value, start.isoformat(), end.isoformat()),
            ).fetchall()

        return [
            Candle(
                symbol=row["symbol"],
                timeframe=Timeframe(row["timeframe"]),
                opened_at=datetime.fromisoformat(row["opened_at"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in rows
        ]

    def count(self) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM candles").fetchone()
        return int(row["count"])

    def record_ingestion_run(self, run: IngestionRun) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                    INSERT INTO ingestion_runs (
                        run_id, provider, symbol, timeframe, requested_start, requested_end,
                        started_at, finished_at, status, fetched_rows, stored_rows,
                        quality_json, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    run.run_id,
                    run.provider,
                    run.symbol,
                    run.timeframe,
                    run.requested_start.isoformat(),
                    run.requested_end.isoformat(),
                    run.started_at.isoformat(),
                    run.finished_at.isoformat(),
                    run.status,
                    run.fetched_rows,
                    run.stored_rows,
                    run.quality_json,
                    run.error,
                ),
            )

    def list_ingestion_runs(self, limit: int = 20) -> list[IngestionRun]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT run_id, provider, symbol, timeframe, requested_start, requested_end,
                       started_at, finished_at, status, fetched_rows, stored_rows,
                       quality_json, error
                FROM ingestion_runs
                ORDER BY finished_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            IngestionRun(
                run_id=row["run_id"],
                provider=row["provider"],
                symbol=row["symbol"],
                timeframe=row["timeframe"],
                requested_start=datetime.fromisoformat(row["requested_start"]),
                requested_end=datetime.fromisoformat(row["requested_end"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=datetime.fromisoformat(row["finished_at"]),
                status=row["status"],
                fetched_rows=row["fetched_rows"],
                stored_rows=row["stored_rows"],
                quality_json=row["quality_json"],
                error=row["error"],
            )
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("only sqlite:/// database URLs are supported in R1")
    return Path(database_url.removeprefix(prefix))
