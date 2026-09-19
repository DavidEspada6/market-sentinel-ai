from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from market_sentinel_ai.domain.market import Candle
from market_sentinel_ai.ports.features import FeatureEngine


@dataclass(frozen=True)
class TrainingExample:
    symbol: str
    timestamp_iso: str
    features: dict[str, float]
    label: int
    realized_return_bps: float


def build_directional_examples(
    candles: Sequence[Candle],
    feature_engine: FeatureEngine,
    horizon_candles: int = 1,
    min_abs_return_bps: float = 0.0,
) -> list[TrainingExample]:
    if horizon_candles <= 0:
        raise ValueError("horizon_candles must be positive")
    if len(candles) <= horizon_candles:
        return []

    feature_rows = feature_engine.transform(candles)
    examples: list[TrainingExample] = []
    for index in range(0, len(candles) - horizon_candles):
        entry_candle = candles[index]
        exit_candle = candles[index + horizon_candles]
        realized_return_bps = (
            (exit_candle.close - entry_candle.close) / entry_candle.close
        ) * 10_000
        if abs(realized_return_bps) < min_abs_return_bps:
            continue

        row = feature_rows[index]
        examples.append(
            TrainingExample(
                symbol=row.symbol,
                timestamp_iso=row.timestamp_iso,
                features=dict(row.values),
                label=1 if realized_return_bps > 0 else 0,
                realized_return_bps=realized_return_bps,
            )
        )
    return examples

