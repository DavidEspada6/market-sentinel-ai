from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import datetime
from pathlib import Path

from market_sentinel_ai.domain.ingestion import IngestionRun
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.operations import AlertRecord, SchedulerRunRecord, SignalRecord

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

CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    direction TEXT NOT NULL,
    probability REAL NOT NULL,
    confidence REAL NOT NULL,
    model_name TEXT NOT NULL,
    expected_return_bps REAL,
    rationale TEXT NOT NULL,
    risk_notes_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_created_at
ON signals(symbol, created_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    external_id TEXT,
    created_at TEXT NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_created_at
ON alerts(created_at DESC);

CREATE TABLE IF NOT EXISTS scheduler_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    symbols_json TEXT NOT NULL,
    signal_count INTEGER NOT NULL,
    alert_count INTEGER NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_scheduler_runs_finished_at
ON scheduler_runs(finished_at DESC);
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

    def record_signal(self, signal: SignalRecord) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO signals (
                    signal_id, symbol, timeframe, generated_at, created_at, direction,
                    probability, confidence, model_name, expected_return_bps, rationale,
                    risk_notes_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.signal_id,
                    signal.symbol,
                    signal.timeframe,
                    signal.generated_at.isoformat(),
                    signal.created_at.isoformat(),
                    signal.direction.value,
                    signal.probability,
                    signal.confidence,
                    signal.model_name,
                    signal.expected_return_bps,
                    signal.rationale,
                    json.dumps(signal.risk_notes, sort_keys=True),
                    json.dumps(signal.metadata, sort_keys=True),
                ),
            )

    def list_signals(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int = 50,
    ) -> list[SignalRecord]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        clauses: list[str] = []
        values: list[object] = []
        if symbol:
            clauses.append("symbol = ?")
            values.append(symbol.upper())
        if timeframe:
            clauses.append("timeframe = ?")
            values.append(timeframe)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT signal_id, symbol, timeframe, generated_at, created_at, direction,
                       probability, confidence, model_name, expected_return_bps, rationale,
                       risk_notes_json, metadata_json
                FROM signals
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*values, limit),
            ).fetchall()
        return [SignalRecord.from_row(row) for row in rows]

    def record_alert(self, alert: AlertRecord) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO alerts (
                    alert_id, signal_id, channel, status, external_id, created_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.alert_id,
                    alert.signal_id,
                    alert.channel,
                    alert.status,
                    alert.external_id,
                    alert.created_at.isoformat(),
                    alert.error,
                ),
            )

    def list_alerts(self, limit: int = 50) -> list[AlertRecord]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT alert_id, signal_id, channel, status, external_id, created_at, error
                FROM alerts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            AlertRecord(
                alert_id=row["alert_id"],
                signal_id=row["signal_id"],
                channel=row["channel"],
                status=row["status"],
                external_id=row["external_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                error=row["error"],
            )
            for row in rows
        ]

    def record_scheduler_run(self, run: SchedulerRunRecord) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO scheduler_runs (
                    run_id, started_at, finished_at, status, symbols_json,
                    signal_count, alert_count, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat(),
                    run.status,
                    json.dumps(run.symbols, sort_keys=True),
                    run.signal_count,
                    run.alert_count,
                    run.error,
                ),
            )

    def list_scheduler_runs(self, limit: int = 20) -> list[SchedulerRunRecord]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT run_id, started_at, finished_at, status, symbols_json,
                       signal_count, alert_count, error
                FROM scheduler_runs
                ORDER BY finished_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            SchedulerRunRecord(
                run_id=row["run_id"],
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=datetime.fromisoformat(row["finished_at"]),
                status=row["status"],
                symbols=tuple(json.loads(row["symbols_json"])),
                signal_count=row["signal_count"],
                alert_count=row["alert_count"],
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
