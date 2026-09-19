from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Event, Lock

from market_sentinel_ai.adapters.market_data import MarketDataProviderError
from market_sentinel_ai.analytics.chart import ChartWindowSpec, chart_window_specs
from market_sentinel_ai.domain.instruments import AssetClass, Instrument
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.operations import PredictionEvaluation
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.operations.service import MarketScanService
from market_sentinel_ai.signals import SignalEngine, build_trade_plan


@dataclass(frozen=True)
class PredictionMonitorRun:
    started_at: datetime
    finished_at: datetime
    generated: int
    resolved: int
    pending: int
    errors: tuple[str, ...]

    @property
    def status(self) -> str:
        return "degraded" if self.errors else "ok"

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "status": self.status,
            "generated": self.generated,
            "resolved": self.resolved,
            "pending": self.pending,
            "errors": list(self.errors),
        }


class PredictionMonitor:
    """Continuously creates one forecast per watchlist/window/candle and scores it later."""

    def __init__(self, service: MarketScanService) -> None:
        self.service = service
        self.repository = service.repository
        self._lock = Lock()
        self._last_run: PredictionMonitorRun | None = None
        self._running = False

    def run_once(self, now: datetime | None = None) -> PredictionMonitorRun:
        started_at = now or datetime.now(tz=UTC)
        generated = 0
        resolved = 0
        errors: list[str] = []
        self._running = True
        try:
            instruments = self.repository.list_watchlist()
            grouped_specs: dict[Timeframe, list[ChartWindowSpec]] = defaultdict(list)
            for spec in chart_window_specs():
                if spec.lookback is not None:
                    grouped_specs[spec.timeframe].append(spec)

            for instrument in instruments:
                if not _market_session_open(instrument, started_at):
                    continue
                for timeframe, specs in grouped_specs.items():
                    try:
                        candles = self._load_candles(instrument, timeframe, specs, started_at)
                        if len(candles) < 2:
                            continue
                        resolved += self._resolve_pending(
                            instrument.symbol,
                            timeframe,
                            candles,
                            started_at,
                        )
                        for spec in specs:
                            generated += self._generate_prediction(
                                instrument,
                                spec,
                                candles,
                                started_at,
                            )
                        # A short history in a provider can contain enough future bars
                        # to resolve an old pending record immediately after ingestion.
                        resolved += self._resolve_pending(
                            instrument.symbol,
                            timeframe,
                            candles,
                            started_at,
                        )
                    except (MarketDataProviderError, OSError, ValueError, RuntimeError) as exc:
                        errors.append(f"{instrument.symbol}/{timeframe.value}: {exc}")
        finally:
            finished_at = datetime.now(tz=UTC)
            pending = len(self.repository.list_predictions(status="pending", limit=100_000))
            result = PredictionMonitorRun(
                started_at=started_at,
                finished_at=finished_at,
                generated=generated,
                resolved=resolved,
                pending=pending,
                errors=tuple(errors),
            )
            with self._lock:
                self._last_run = result
                self._running = False
        return result

    def run_forever(self, stop_event: Event, interval_seconds: int = 30) -> None:
        while not stop_event.is_set():
            self.run_once()
            stop_event.wait(max(5, interval_seconds))

    def status(self) -> dict[str, object]:
        with self._lock:
            last_run = self._last_run
            running = self._running
        pending = len(self.repository.list_predictions(status="pending", limit=100_000))
        return {
            "running": running,
            "pending": pending,
            "last_run": last_run.to_dict() if last_run else None,
            "interval_seconds": 30,
            "watchlist_size": len(self.repository.list_watchlist()),
            "windows": [spec.window.value for spec in chart_window_specs() if spec.lookback],
        }

    def _load_candles(
        self,
        instrument: Instrument,
        timeframe: Timeframe,
        specs: list[ChartWindowSpec],
        end: datetime,
    ) -> list[Candle]:
        lookback = _monitor_lookback(timeframe, specs)
        start = end - lookback
        fetched = sorted(
            [
                candle
                for candle in self.service.provider.historical_candles(
                    instrument.market_symbol,
                    timeframe,
                    start,
                    end,
                )
                if start <= candle.opened_at < end
            ],
            key=lambda candle: candle.opened_at,
        )
        if fetched:
            self.repository.upsert_many(fetched)
            return fetched
        return self.repository.list_candles(instrument.market_symbol, timeframe, start, end)

    def _generate_prediction(
        self,
        instrument: Instrument,
        spec: ChartWindowSpec,
        candles: list[Candle],
        now: datetime,
    ) -> int:
        assert spec.lookback is not None
        horizon_minutes = max(1, int(spec.lookback.total_seconds() // 60))
        cost_bps = (
            self.service.settings.risk.default_fee_bps * 2
            + self.service.settings.risk.default_slippage_bps * 2
            + self.service.settings.risk.default_spread_bps
        )
        prediction, features = self.service.predict_market(
            candles,
            spec.timeframe,
            cost_bps,
            horizon_minutes=horizon_minutes,
        )
        signal = SignalEngine(
            min_probability=0.55,
            min_expected_return_bps=cost_bps,
        ).from_prediction(prediction)
        latest = candles[-1]
        plan = build_trade_plan(
            signal,
            latest,
            features[-1],
            spec.timeframe,
            cost_bps,
        )
        prediction_key = f"{instrument.symbol}:{spec.window.value}:{latest.opened_at.isoformat()}"
        record = PredictionEvaluation(
            prediction_id=f"pred-{prediction_key}",
            prediction_key=prediction_key,
            symbol=instrument.symbol,
            timeframe=spec.timeframe.value,
            window=spec.window.value,
            horizon_minutes=horizon_minutes,
            generated_at=prediction.generated_at,
            reference_time=latest.opened_at,
            reference_price=latest.close,
            direction=prediction.direction,
            probability=prediction.probability,
            confidence=signal.confidence,
            model_name=prediction.model_name,
            expected_return_bps=prediction.expected_return_bps,
            evaluation_threshold_bps=max(cost_bps, 1.0),
            due_at=latest.opened_at + spec.lookback,
            status="pending",
            metadata={
                "provider": str(getattr(self.service.provider, "provider_name", "unknown")),
                "action": plan.action,
                **plan.to_metadata(),
            },
        )
        return int(self.repository.record_prediction(record))

    def _resolve_pending(
        self,
        symbol: str,
        timeframe: Timeframe,
        candles: list[Candle],
        now: datetime,
    ) -> int:
        resolved = 0
        pending = self.repository.list_predictions(
            symbol=symbol,
            timeframe=timeframe.value,
            status="pending",
            limit=10_000,
        )
        step = timedelta(minutes=_timeframe_minutes(timeframe))
        for prediction in pending:
            if prediction.due_at > now:
                continue
            actual = next(
                (
                    candle
                    for candle in candles
                    if candle.opened_at >= prediction.due_at
                    and candle.opened_at >= prediction.reference_time + step
                ),
                None,
            )
            if actual is None or prediction.reference_price <= 0:
                continue
            actual_return_bps = (
                (actual.close - prediction.reference_price) / prediction.reference_price * 10_000
            )
            threshold = prediction.evaluation_threshold_bps
            correct = _prediction_is_correct(prediction.direction, actual_return_bps, threshold)
            if self.repository.resolve_prediction(
                prediction.prediction_id,
                actual_price=actual.close,
                actual_return_bps=actual_return_bps,
                correct=correct,
                resolved_at=now,
            ):
                resolved += 1
        return resolved


def _prediction_is_correct(
    direction: Direction,
    actual_return_bps: float,
    threshold: float,
) -> bool:
    if direction is Direction.LONG:
        return actual_return_bps > threshold
    if direction is Direction.SHORT:
        return actual_return_bps < -threshold
    return abs(actual_return_bps) <= threshold


def _market_session_open(instrument: Instrument, timestamp: datetime) -> bool:
    """Avoid weekend forecasts for exchange-traded assets; crypto runs 24/7."""
    if instrument.asset_class is AssetClass.CRYPTO:
        return True
    return timestamp.weekday() < 5


def _monitor_lookback(timeframe: Timeframe, specs: list[ChartWindowSpec]) -> timedelta:
    largest_window = max(
        spec.lookback or timedelta(0) for spec in specs
    )
    training_padding = {
        Timeframe.ONE_MINUTE: timedelta(days=7),
        Timeframe.FIVE_MINUTES: timedelta(days=60),
        Timeframe.FIFTEEN_MINUTES: timedelta(days=90),
        Timeframe.ONE_HOUR: timedelta(days=180),
        Timeframe.ONE_DAY: timedelta(days=3650),
    }[timeframe]
    return max(largest_window + training_padding, training_padding)


def _timeframe_minutes(timeframe: Timeframe) -> int:
    return {
        Timeframe.ONE_MINUTE: 1,
        Timeframe.FIVE_MINUTES: 5,
        Timeframe.FIFTEEN_MINUTES: 15,
        Timeframe.ONE_HOUR: 60,
        Timeframe.ONE_DAY: 1440,
    }[timeframe]
