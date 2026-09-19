from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from market_sentinel_ai.domain.market import Candle, Timeframe

_TIMEFRAME_STEPS: dict[Timeframe, timedelta] = {
    Timeframe.ONE_MINUTE: timedelta(minutes=1),
    Timeframe.FIVE_MINUTES: timedelta(minutes=5),
    Timeframe.FIFTEEN_MINUTES: timedelta(minutes=15),
    Timeframe.ONE_HOUR: timedelta(hours=1),
    Timeframe.ONE_DAY: timedelta(days=1),
}


@dataclass(frozen=True)
class CandleQualityReport:
    rows: int
    duplicate_timestamps: int
    out_of_order: int
    missing_intervals: int
    stale_seconds: float | None

    @property
    def accepted(self) -> bool:
        return self.rows > 0 and self.duplicate_timestamps == 0 and self.out_of_order == 0


def analyze_candle_sequence(
    candles: Sequence[Candle],
    *,
    observed_at: datetime | None = None,
) -> CandleQualityReport:
    if not candles:
        return CandleQualityReport(0, 0, 0, 0, None)

    duplicate_timestamps = 0
    out_of_order = 0
    missing_intervals = 0
    seen: set[datetime] = set()
    step = _TIMEFRAME_STEPS[candles[0].timeframe]
    previous: Candle | None = None

    for candle in candles:
        if candle.opened_at in seen:
            duplicate_timestamps += 1
        seen.add(candle.opened_at)
        if previous is not None:
            if candle.opened_at < previous.opened_at:
                out_of_order += 1
            elif _is_expected_contiguous_session(previous, candle):
                gap = candle.opened_at - previous.opened_at
                if gap > step:
                    missing_intervals += max(0, int(gap / step) - 1)
        previous = candle

    now = observed_at or datetime.now(tz=UTC)
    latest = max(candle.opened_at for candle in candles)
    stale_seconds = max(0.0, (now.astimezone(UTC) - latest.astimezone(UTC)).total_seconds())
    return CandleQualityReport(
        rows=len(candles),
        duplicate_timestamps=duplicate_timestamps,
        out_of_order=out_of_order,
        missing_intervals=missing_intervals,
        stale_seconds=stale_seconds,
    )


def _is_expected_contiguous_session(previous: Candle, current: Candle) -> bool:
    if previous.timeframe is Timeframe.ONE_DAY:
        return False
    return previous.opened_at.astimezone(UTC).date() == current.opened_at.astimezone(UTC).date()


def validate_candle_sequence(candles: Sequence[Candle]) -> None:
    if not candles:
        return

    previous = candles[0]
    for candle in candles[1:]:
        if candle.symbol != previous.symbol:
            raise ValueError("all candles in a sequence must share the same symbol")
        if candle.timeframe != previous.timeframe:
            raise ValueError("all candles in a sequence must share the same timeframe")
        if candle.opened_at <= previous.opened_at:
            raise ValueError("candles must be strictly ordered by opened_at")
        previous = candle
