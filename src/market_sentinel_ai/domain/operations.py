from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from market_sentinel_ai.domain.prediction import Direction, Signal

MetadataValue = str | float | int | bool


@dataclass(frozen=True)
class SignalRecord:
    signal_id: str
    symbol: str
    timeframe: str
    generated_at: datetime
    created_at: datetime
    direction: Direction
    probability: float
    confidence: float
    model_name: str
    expected_return_bps: float | None
    rationale: str
    risk_notes: tuple[str, ...]
    metadata: dict[str, MetadataValue]

    @classmethod
    def from_signal(cls, signal_id: str, timeframe: str, signal: Signal) -> SignalRecord:
        now = datetime.now(tz=signal.prediction.generated_at.tzinfo)
        return cls(
            signal_id=signal_id,
            symbol=signal.prediction.symbol,
            timeframe=timeframe,
            generated_at=signal.prediction.generated_at,
            created_at=now,
            direction=signal.prediction.direction,
            probability=signal.prediction.probability,
            confidence=signal.confidence,
            model_name=signal.prediction.model_name,
            expected_return_bps=signal.prediction.expected_return_bps,
            rationale=signal.rationale,
            risk_notes=signal.risk_notes,
            metadata=dict(signal.prediction.metadata),
        )

    @classmethod
    def from_row(cls, row: object) -> SignalRecord:
        record = row
        return cls(
            signal_id=record["signal_id"],
            symbol=record["symbol"],
            timeframe=record["timeframe"],
            generated_at=datetime.fromisoformat(record["generated_at"]),
            created_at=datetime.fromisoformat(record["created_at"]),
            direction=Direction(record["direction"]),
            probability=record["probability"],
            confidence=record["confidence"],
            model_name=record["model_name"],
            expected_return_bps=record["expected_return_bps"],
            rationale=record["rationale"],
            risk_notes=tuple(json.loads(record["risk_notes_json"])),
            metadata=json.loads(record["metadata_json"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "generated_at": self.generated_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "direction": self.direction.value,
            "probability": self.probability,
            "confidence": self.confidence,
            "model_name": self.model_name,
            "expected_return_bps": self.expected_return_bps,
            "rationale": self.rationale,
            "risk_notes": list(self.risk_notes),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PredictionEvaluation:
    prediction_id: str
    prediction_key: str
    symbol: str
    timeframe: str
    window: str
    horizon_minutes: int
    generated_at: datetime
    reference_time: datetime
    reference_price: float
    direction: Direction
    probability: float
    confidence: float
    model_name: str
    expected_return_bps: float | None
    evaluation_threshold_bps: float
    due_at: datetime
    status: str
    actual_price: float | None = None
    actual_return_bps: float | None = None
    correct: bool | None = None
    resolved_at: datetime | None = None
    metadata: dict[str, MetadataValue] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: object) -> PredictionEvaluation:
        return cls(
            prediction_id=row["prediction_id"],
            prediction_key=row["prediction_key"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            window=row["window"],
            horizon_minutes=row["horizon_minutes"],
            generated_at=datetime.fromisoformat(row["generated_at"]),
            reference_time=datetime.fromisoformat(row["reference_time"]),
            reference_price=row["reference_price"],
            direction=Direction(row["direction"]),
            probability=row["probability"],
            confidence=row["confidence"],
            model_name=row["model_name"],
            expected_return_bps=row["expected_return_bps"],
            evaluation_threshold_bps=row["evaluation_threshold_bps"],
            due_at=datetime.fromisoformat(row["due_at"]),
            status=row["status"],
            actual_price=row["actual_price"],
            actual_return_bps=row["actual_return_bps"],
            correct=None if row["correct"] is None else bool(row["correct"]),
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"])
                if row["resolved_at"]
                else None
            ),
            metadata=json.loads(row["metadata_json"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "prediction_id": self.prediction_id,
            "prediction_key": self.prediction_key,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "window": self.window,
            "horizon_minutes": self.horizon_minutes,
            "generated_at": self.generated_at.isoformat(),
            "reference_time": self.reference_time.isoformat(),
            "reference_price": self.reference_price,
            "direction": self.direction.value,
            "probability": self.probability,
            "confidence": self.confidence,
            "model_name": self.model_name,
            "expected_return_bps": self.expected_return_bps,
            "evaluation_threshold_bps": self.evaluation_threshold_bps,
            "due_at": self.due_at.isoformat(),
            "status": self.status,
            "actual_price": self.actual_price,
            "actual_return_bps": self.actual_return_bps,
            "correct": self.correct,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class AlertRecord:
    alert_id: str
    signal_id: str
    channel: str
    status: str
    external_id: str | None
    created_at: datetime
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "alert_id": self.alert_id,
            "signal_id": self.signal_id,
            "channel": self.channel,
            "status": self.status,
            "external_id": self.external_id,
            "created_at": self.created_at.isoformat(),
            "error": self.error,
        }


@dataclass(frozen=True)
class SchedulerRunRecord:
    run_id: str
    started_at: datetime
    finished_at: datetime
    status: str
    symbols: tuple[str, ...]
    signal_count: int
    alert_count: int
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "status": self.status,
            "symbols": list(self.symbols),
            "signal_count": self.signal_count,
            "alert_count": self.alert_count,
            "error": self.error,
        }
