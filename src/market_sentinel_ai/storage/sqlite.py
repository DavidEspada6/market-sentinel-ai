from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from market_sentinel_ai.domain.ingestion import IngestionRun
from market_sentinel_ai.domain.instruments import AssetClass, Instrument, featured_instruments
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.operations import (
    AlertRecord,
    PredictionEvaluation,
    SchedulerRunRecord,
    SignalRecord,
)
from market_sentinel_ai.domain.paper import (
    PaperAccountSnapshot,
    PaperPosition,
    PaperTrade,
    PaperTradeRecord,
)
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.monitoring.drift import DriftReport

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

CREATE TABLE IF NOT EXISTS prediction_evaluations (
    prediction_id TEXT PRIMARY KEY,
    prediction_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    window TEXT NOT NULL,
    horizon_minutes INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    reference_time TEXT NOT NULL,
    reference_price REAL NOT NULL,
    direction TEXT NOT NULL,
    probability REAL NOT NULL,
    confidence REAL NOT NULL,
    model_name TEXT NOT NULL,
    expected_return_bps REAL,
    evaluation_threshold_bps REAL NOT NULL,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL,
    actual_price REAL,
    actual_return_bps REAL,
    correct INTEGER,
    resolved_at TEXT,
    metadata_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prediction_evaluations_status_due_at
ON prediction_evaluations(status, due_at);

CREATE INDEX IF NOT EXISTS idx_prediction_evaluations_symbol_window
ON prediction_evaluations(symbol, window, generated_at DESC);

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

CREATE TABLE IF NOT EXISTS paper_accounts (
    account_id TEXT PRIMARY KEY,
    starting_equity REAL NOT NULL,
    equity REAL NOT NULL,
    updated_at TEXT NOT NULL,
    real_execution_enabled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS paper_trades (
    trade_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    quantity REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    pnl REAL NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT NOT NULL,
    margin REAL NOT NULL DEFAULT 0,
    leverage REAL NOT NULL DEFAULT 1,
    entry_cost REAL NOT NULL DEFAULT 0,
    exit_cost REAL NOT NULL DEFAULT 0,
    notional REAL NOT NULL DEFAULT 0,
    close_reason TEXT NOT NULL DEFAULT 'manual'
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_account_closed_at
ON paper_trades(account_id, closed_at DESC);

CREATE TABLE IF NOT EXISTS paper_positions (
    position_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    quantity REAL NOT NULL,
    entry_price REAL NOT NULL,
    mark_price REAL NOT NULL,
    leverage REAL NOT NULL,
    margin REAL NOT NULL,
    entry_cost REAL NOT NULL,
    opened_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_account_updated_at
ON paper_positions(account_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS drift_reports (
    report_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    drifted INTEGER NOT NULL,
    threshold REAL NOT NULL,
    scores_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_drift_reports_created_at
ON drift_reports(created_at DESC);

CREATE TABLE IF NOT EXISTS health_checks (
    check_id TEXT PRIMARY KEY,
    check_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_health_checks_created_at
ON health_checks(created_at DESC);

CREATE TABLE IF NOT EXISTS watchlist (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    exchange TEXT NOT NULL,
    currency TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    featured INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_watchlist_enabled_symbol
ON watchlist(enabled, symbol);
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

    def latest_ingestion_run(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> IngestionRun | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT run_id, provider, symbol, timeframe, requested_start, requested_end,
                       started_at, finished_at, status, fetched_rows, stored_rows,
                       quality_json, error
                FROM ingestion_runs
                WHERE symbol = ? AND timeframe = ?
                ORDER BY finished_at DESC
                LIMIT 1
                """,
                (symbol.upper(), timeframe.value),
            ).fetchone()
        if row is None:
            return None
        return IngestionRun(
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

    def record_prediction(self, prediction: PredictionEvaluation) -> bool:
        """Persist one prediction, returning False when its evaluation key already exists."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO prediction_evaluations (
                    prediction_id, prediction_key, symbol, timeframe, window,
                    horizon_minutes, generated_at, reference_time, reference_price,
                    direction, probability, confidence, model_name, expected_return_bps,
                    evaluation_threshold_bps, due_at, status, actual_price,
                    actual_return_bps, correct, resolved_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction.prediction_id,
                    prediction.prediction_key,
                    prediction.symbol,
                    prediction.timeframe,
                    prediction.window,
                    prediction.horizon_minutes,
                    prediction.generated_at.isoformat(),
                    prediction.reference_time.isoformat(),
                    prediction.reference_price,
                    prediction.direction.value,
                    prediction.probability,
                    prediction.confidence,
                    prediction.model_name,
                    prediction.expected_return_bps,
                    prediction.evaluation_threshold_bps,
                    prediction.due_at.isoformat(),
                    prediction.status,
                    prediction.actual_price,
                    prediction.actual_return_bps,
                    None if prediction.correct is None else int(prediction.correct),
                    prediction.resolved_at.isoformat() if prediction.resolved_at else None,
                    json.dumps(prediction.metadata, sort_keys=True),
                ),
            )
        return cursor.rowcount == 1

    def list_predictions(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        window: str | None = None,
        status: str | None = None,
        limit: int = 500,
    ) -> list[PredictionEvaluation]:
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
        if window:
            clauses.append("window = ?")
            values.append(window)
        if status:
            clauses.append("status = ?")
            values.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT prediction_id, prediction_key, symbol, timeframe, window,
                       horizon_minutes, generated_at, reference_time, reference_price,
                       direction, probability, confidence, model_name, expected_return_bps,
                       evaluation_threshold_bps, due_at, status, actual_price,
                       actual_return_bps, correct, resolved_at, metadata_json
                FROM prediction_evaluations
                {where}
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (*values, limit),
            ).fetchall()
        return [PredictionEvaluation.from_row(row) for row in rows]

    def resolve_prediction(
        self,
        prediction_id: str,
        *,
        actual_price: float,
        actual_return_bps: float,
        correct: bool,
        resolved_at: datetime,
    ) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE prediction_evaluations
                SET status = 'resolved', actual_price = ?, actual_return_bps = ?,
                    correct = ?, resolved_at = ?
                WHERE prediction_id = ? AND status = 'pending'
                """,
                (
                    actual_price,
                    actual_return_bps,
                    int(correct),
                    resolved_at.isoformat(),
                    prediction_id,
                ),
            )
        return cursor.rowcount == 1

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

    def add_watchlist_item(self, instrument: Instrument) -> Instrument:
        now = datetime.now(tz=UTC).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO watchlist (
                    symbol, name, asset_class, exchange, currency, provider_symbol,
                    featured, enabled, added_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    asset_class = excluded.asset_class,
                    exchange = excluded.exchange,
                    currency = excluded.currency,
                    provider_symbol = excluded.provider_symbol,
                    featured = excluded.featured,
                    enabled = 1
                """,
                (
                    instrument.symbol,
                    instrument.name,
                    instrument.asset_class.value,
                    instrument.exchange,
                    instrument.currency,
                    instrument.market_symbol,
                    int(instrument.featured),
                    now,
                ),
            )
        return instrument

    def remove_watchlist_item(self, symbol: str) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE watchlist SET enabled = 0 WHERE symbol = ? AND enabled = 1",
                (symbol.upper(),),
            )
        return cursor.rowcount > 0

    def list_watchlist(self, enabled_only: bool = True) -> list[Instrument]:
        where = "WHERE enabled = 1" if enabled_only else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT symbol, name, asset_class, exchange, currency, provider_symbol, featured
                FROM watchlist
                {where}
                ORDER BY symbol ASC
                """
            ).fetchall()
        return [
            Instrument(
                symbol=row["symbol"],
                name=row["name"],
                asset_class=AssetClass(row["asset_class"]),
                exchange=row["exchange"],
                currency=row["currency"],
                provider_symbol=row["provider_symbol"],
                featured=bool(row["featured"]),
            )
            for row in rows
        ]

    def load_paper_account(self, account_id: str) -> PaperAccountSnapshot | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT account_id, starting_equity, equity, updated_at, real_execution_enabled
                FROM paper_accounts
                WHERE account_id = ?
                """,
                (account_id,),
            ).fetchone()
        if row is None:
            return None
        return PaperAccountSnapshot(
            account_id=row["account_id"],
            starting_equity=row["starting_equity"],
            equity=row["equity"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
            real_execution_enabled=bool(row["real_execution_enabled"]),
        )

    def save_paper_account(self, snapshot: PaperAccountSnapshot) -> None:
        if snapshot.real_execution_enabled:
            raise ValueError("real execution is disabled for paper accounts")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO paper_accounts (
                    account_id, starting_equity, equity, updated_at, real_execution_enabled
                ) VALUES (?, ?, ?, ?, 0)
                ON CONFLICT(account_id) DO UPDATE SET
                    starting_equity = excluded.starting_equity,
                    equity = excluded.equity,
                    updated_at = excluded.updated_at,
                    real_execution_enabled = 0
                """,
                (
                    snapshot.account_id,
                    snapshot.starting_equity,
                    snapshot.equity,
                    snapshot.updated_at.isoformat(),
                ),
            )

    def record_paper_trade(self, record: PaperTradeRecord) -> None:
        trade = record.trade
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO paper_trades (
                    trade_id, account_id, symbol, direction, quantity, entry_price,
                    exit_price, pnl, opened_at, closed_at, margin, leverage,
                    entry_cost, exit_cost, notional, close_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.trade_id,
                    record.account_id,
                    trade.symbol,
                    trade.direction.value,
                    trade.quantity,
                    trade.entry_price,
                    trade.exit_price,
                    trade.pnl,
                    trade.opened_at.isoformat(),
                    trade.closed_at.isoformat(),
                    trade.margin,
                    trade.leverage,
                    trade.entry_cost,
                    trade.exit_cost,
                    trade.notional or trade.quantity * trade.entry_price,
                    trade.close_reason,
                ),
            )

    def list_paper_trades(self, account_id: str, limit: int = 500) -> list[PaperTradeRecord]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT trade_id, account_id, symbol, direction, quantity, entry_price,
                       exit_price, pnl, opened_at, closed_at, margin, leverage,
                       entry_cost, exit_cost, notional, close_reason
                FROM paper_trades
                WHERE account_id = ?
                ORDER BY closed_at ASC
                LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
        return [
            PaperTradeRecord(
                trade_id=row["trade_id"],
                account_id=row["account_id"],
                trade=PaperTrade(
                    symbol=row["symbol"],
                    direction=Direction(row["direction"]),
                    quantity=row["quantity"],
                    entry_price=row["entry_price"],
                    exit_price=row["exit_price"],
                    pnl=row["pnl"],
                    opened_at=datetime.fromisoformat(row["opened_at"]),
                    closed_at=datetime.fromisoformat(row["closed_at"]),
                    margin=row["margin"],
                    leverage=row["leverage"],
                    entry_cost=row["entry_cost"],
                    exit_cost=row["exit_cost"],
                    notional=row["notional"],
                    close_reason=row["close_reason"],
                ),
            )
            for row in rows
        ]

    def save_paper_position(self, position: PaperPosition) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO paper_positions (
                    position_id, account_id, symbol, direction, quantity, entry_price,
                    mark_price, leverage, margin, entry_cost, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(position_id) DO UPDATE SET
                    mark_price = excluded.mark_price,
                    updated_at = excluded.updated_at
                """,
                (
                    position.position_id,
                    position.account_id,
                    position.symbol,
                    position.direction.value,
                    position.quantity,
                    position.entry_price,
                    position.mark_price,
                    position.leverage,
                    position.margin,
                    position.entry_cost,
                    position.opened_at.isoformat(),
                    position.updated_at.isoformat(),
                ),
            )

    def list_paper_positions(self, account_id: str) -> list[PaperPosition]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT position_id, account_id, symbol, direction, quantity, entry_price,
                       mark_price, leverage, margin, entry_cost, opened_at, updated_at
                FROM paper_positions
                WHERE account_id = ?
                ORDER BY opened_at ASC
                """,
                (account_id,),
            ).fetchall()
        return [
            PaperPosition(
                position_id=row["position_id"],
                account_id=row["account_id"],
                symbol=row["symbol"],
                direction=Direction(row["direction"]),
                quantity=row["quantity"],
                entry_price=row["entry_price"],
                mark_price=row["mark_price"],
                leverage=row["leverage"],
                margin=row["margin"],
                entry_cost=row["entry_cost"],
                opened_at=datetime.fromisoformat(row["opened_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def delete_paper_position(self, account_id: str, position_id: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM paper_positions WHERE account_id = ? AND position_id = ?",
                (account_id, position_id),
            )

    def reset_paper_account(self, account_id: str, snapshot: PaperAccountSnapshot) -> None:
        if snapshot.real_execution_enabled:
            raise ValueError("real execution is disabled for paper accounts")
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM paper_positions WHERE account_id = ?", (account_id,))
            connection.execute("DELETE FROM paper_trades WHERE account_id = ?", (account_id,))
            connection.execute("DELETE FROM paper_accounts WHERE account_id = ?", (account_id,))
            connection.execute(
                """
                INSERT INTO paper_accounts (
                    account_id, starting_equity, equity, updated_at, real_execution_enabled
                ) VALUES (?, ?, ?, ?, 0)
                """,
                (
                    snapshot.account_id,
                    snapshot.starting_equity,
                    snapshot.equity,
                    snapshot.updated_at.isoformat(),
                ),
            )

    def record_drift_report(
        self,
        symbol: str,
        model_name: str,
        report: DriftReport,
    ) -> str:
        report_id = str(uuid4())
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO drift_reports (
                    report_id, symbol, model_name, created_at, drifted, threshold, scores_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    symbol.upper(),
                    model_name,
                    datetime.now(tz=UTC).isoformat(),
                    int(report.drifted),
                    report.threshold,
                    json.dumps(report.scores, sort_keys=True),
                ),
            )
        return report_id

    def list_drift_reports(self, limit: int = 50) -> list[dict[str, object]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT report_id, symbol, model_name, created_at, drifted, threshold, scores_json
                FROM drift_reports
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "report_id": row["report_id"],
                "symbol": row["symbol"],
                "model_name": row["model_name"],
                "created_at": row["created_at"],
                "drifted": bool(row["drifted"]),
                "threshold": row["threshold"],
                "scores": json.loads(row["scores_json"]),
            }
            for row in rows
        ]

    def record_health_check(
        self,
        check_name: str,
        status: str,
        details: dict[str, object],
    ) -> str:
        check_id = str(uuid4())
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO health_checks (
                    check_id, check_name, created_at, status, details_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    check_id,
                    check_name,
                    datetime.now(tz=UTC).isoformat(),
                    status,
                    json.dumps(details, sort_keys=True, default=str),
                ),
            )
        return check_id

    def list_health_checks(self, limit: int = 50) -> list[dict[str, object]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT check_id, check_name, created_at, status, details_json
                FROM health_checks
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "check_id": row["check_id"],
                "check_name": row["check_name"],
                "created_at": row["created_at"],
                "status": row["status"],
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]

    def health_status(self) -> dict[str, object]:
        try:
            with closing(self._connect()) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            return {"status": "ok" if integrity == "ok" else "degraded", "integrity": integrity}
        except sqlite3.Error as exc:
            return {"status": "failed", "error": str(exc)}

    def backup_to(self, destination: str | Path) -> Path:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        source = self._connect()
        target = sqlite3.connect(destination_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        return destination_path

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(SCHEMA)
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(paper_trades)").fetchall()
            }
            migrations = {
                "margin": "ALTER TABLE paper_trades ADD COLUMN margin REAL NOT NULL DEFAULT 0",
                "leverage": "ALTER TABLE paper_trades ADD COLUMN leverage REAL NOT NULL DEFAULT 1",
                "entry_cost": (
                    "ALTER TABLE paper_trades ADD COLUMN entry_cost REAL NOT NULL DEFAULT 0"
                ),
                "exit_cost": (
                    "ALTER TABLE paper_trades ADD COLUMN exit_cost REAL NOT NULL DEFAULT 0"
                ),
                "notional": "ALTER TABLE paper_trades ADD COLUMN notional REAL NOT NULL DEFAULT 0",
                "close_reason": (
                    "ALTER TABLE paper_trades ADD COLUMN close_reason TEXT NOT NULL "
                    "DEFAULT 'manual'"
                ),
            }
            for column, statement in migrations.items():
                if column not in existing_columns:
                    connection.execute(statement)
            connection.execute(
                """
                UPDATE paper_trades
                SET notional = quantity * entry_price
                WHERE notional = 0
                """
            )
            if connection.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0] == 0:
                for instrument in featured_instruments():
                    connection.execute(
                        """
                        INSERT INTO watchlist (
                            symbol, name, asset_class, exchange, currency, provider_symbol,
                            featured, enabled, added_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            instrument.symbol,
                            instrument.name,
                            instrument.asset_class.value,
                            instrument.exchange,
                            instrument.currency,
                            instrument.market_symbol,
                            int(instrument.featured),
                            datetime.now(tz=UTC).isoformat(),
                        ),
                    )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("only sqlite:/// database URLs are supported in R1")
    return Path(database_url.removeprefix(prefix))
