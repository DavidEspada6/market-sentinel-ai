from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class Prediction:
    symbol: str
    horizon_minutes: int
    direction: Direction
    probability: float
    model_name: str
    generated_at: datetime
    expected_return_bps: float | None = None
    metadata: dict[str, str | float | int | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.probability <= 1:
            raise ValueError("probability must be between 0 and 1")
        if self.horizon_minutes <= 0:
            raise ValueError("horizon_minutes must be positive")


@dataclass(frozen=True)
class Signal:
    prediction: Prediction
    confidence: float
    rationale: str
    risk_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def is_actionable(self) -> bool:
        return self.prediction.direction is not Direction.NO_TRADE and self.confidence >= 0.5

