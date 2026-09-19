from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from market_sentinel_ai.adapters.market_data import build_market_data_provider
from market_sentinel_ai.alerts import DryRunAlertChannel, JsonlAlertChannel, WebhookAlertChannel
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.operations import AlertRecord, SignalRecord
from market_sentinel_ai.domain.prediction import Prediction
from market_sentinel_ai.features import OHLCVFeatureEngine
from market_sentinel_ai.ingestion import MarketDataIngestionService
from market_sentinel_ai.models import AdaptiveDirectionalModel, MomentumBaselineModel
from market_sentinel_ai.ports.features import FeatureRow
from market_sentinel_ai.signals import SignalEngine, build_trade_plan
from market_sentinel_ai.storage import SQLiteCandleRepository, sqlite_path_from_url


@dataclass(frozen=True)
class ScanResult:
    signal: SignalRecord
    alerts: tuple[AlertRecord, ...]
    candle_count: int
    ingestion_run_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "signal": self.signal.to_dict(),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "candle_count": self.candle_count,
            "ingestion_run_id": self.ingestion_run_id,
        }


class MarketScanService:
    def __init__(
        self,
        settings: Settings,
        repository: SQLiteCandleRepository | None = None,
        provider: object | None = None,
        alert_channel: object | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or SQLiteCandleRepository(
            sqlite_path_from_url(settings.database_url)
        )
        self.provider = provider or build_market_data_provider(settings.market_data)
        self.alert_channel = alert_channel or _build_alert_channel(settings)
        self._adaptive_models: dict[
            tuple[str, str], tuple[tuple[int, str, float], AdaptiveDirectionalModel]
        ] = {}
        self._model_status: dict[tuple[str, str], dict[str, str | float | int | bool]] = {}

    def scan(self, symbol: str, timeframe: Timeframe, days: int = 5) -> ScanResult:
        if not symbol.strip():
            raise ValueError("symbol cannot be empty")
        if days <= 0:
            raise ValueError("days must be positive")

        end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        start = end - timedelta(days=days)
        ingestion = MarketDataIngestionService(self.provider, self.repository).ingest(
            symbol, timeframe, start, end
        )
        candles = self.repository.list_candles(symbol, timeframe, start, end)
        if len(candles) < 2:
            raise ValueError("at least two candles are required to generate a signal")

        round_trip_cost_bps = (
            self.settings.risk.default_fee_bps * 2
            + self.settings.risk.default_slippage_bps * 2
            + self.settings.risk.default_spread_bps
        )
        prediction, features = self.predict_market(candles, timeframe, round_trip_cost_bps)
        signal = SignalEngine(
            min_probability=0.55,
            min_expected_return_bps=round_trip_cost_bps,
        ).from_prediction(prediction)
        plan = build_trade_plan(
            signal,
            candles[-1],
            features[-1],
            timeframe,
            round_trip_cost_bps,
        )
        record = SignalRecord.from_signal(str(uuid4()), timeframe.value, signal)
        record = replace(record, metadata={**record.metadata, **plan.to_metadata()})
        self.repository.record_signal(record)

        alerts: list[AlertRecord] = []
        if signal.is_actionable:
            alerts.append(
                self._send_alert(record, signal)
                if not self._is_duplicate_actionable_signal(record)
                else self._suppress_alert(record)
            )

        return ScanResult(
            signal=record,
            alerts=tuple(alerts),
            candle_count=len(candles),
            ingestion_run_id=ingestion.run.run_id,
        )

    def predict_market(
        self,
        candles: Sequence[Candle],
        timeframe: Timeframe,
        round_trip_cost_bps: float,
    ) -> tuple[Prediction, list[FeatureRow]]:
        """Return the adaptive prediction, falling back transparently when untrainable."""
        if not candles:
            raise ValueError("candles cannot be empty")
        features = OHLCVFeatureEngine().transform(candles)
        candle_minutes = _timeframe_minutes(timeframe)
        horizon_minutes = candle_minutes * 3
        key = (candles[-1].symbol, timeframe.value)
        signature = (len(candles), candles[-1].opened_at.isoformat(), round_trip_cost_bps)
        cached = self._adaptive_models.get(key)
        if cached is None or cached[0] != signature:
            model = AdaptiveDirectionalModel(horizon_minutes=horizon_minutes)
            try:
                model.fit(candles, features, round_trip_cost_bps)
                self._adaptive_models[key] = (signature, model)
                self._model_status[key] = {
                    "symbol": candles[-1].symbol,
                    "timeframe": timeframe.value,
                    "updated_at": datetime.now(tz=UTC).isoformat(),
                    **model.status,
                }
            except (RuntimeError, ValueError) as exc:
                self._model_status[key] = {
                    "symbol": candles[-1].symbol,
                    "timeframe": timeframe.value,
                    "updated_at": datetime.now(tz=UTC).isoformat(),
                    "status": "fallback",
                    "model": "momentum-baseline",
                    "reason": str(exc),
                    "training_samples": 0,
                    "oos_folds": 0,
                    "oos_recall": 0.0,
                    "real_orders_enabled": False,
                }
                self._adaptive_models.pop(key, None)
        if cached is not None and cached[0] == signature:
            model = cached[1]
        elif key in self._adaptive_models:
            model = self._adaptive_models[key][1]
        else:
            model = None

        if model is not None:
            return model.predict(features), features
        return MomentumBaselineModel(horizon_minutes=candle_minutes).predict(features), features

    def model_status(self) -> list[dict[str, str | float | int | bool]]:
        return [dict(self._model_status[key]) for key in sorted(self._model_status)]

    def _send_alert(self, record: SignalRecord, signal: object) -> AlertRecord:
        created_at = datetime.now(tz=UTC)
        try:
            external_id = self.alert_channel.send(signal)
            alert = AlertRecord(
                alert_id=str(uuid4()),
                signal_id=record.signal_id,
                channel=self.alert_channel.channel_name,
                status="sent",
                external_id=external_id,
                created_at=created_at,
            )
        except Exception as exc:
            alert = AlertRecord(
                alert_id=str(uuid4()),
                signal_id=record.signal_id,
                channel=self.alert_channel.channel_name,
                status="failed",
                external_id=None,
                created_at=created_at,
                error=str(exc),
            )
        self.repository.record_alert(alert)
        return alert

    def _is_duplicate_actionable_signal(self, record: SignalRecord) -> bool:
        if self.settings.alerts.dedupe_minutes <= 0:
            return False
        recent = self.repository.list_signals(
            symbol=record.symbol,
            timeframe=record.timeframe,
            limit=2,
        )
        if len(recent) < 2:
            return False
        previous = recent[1]
        age_seconds = (record.created_at - previous.created_at).total_seconds()
        return (
            0 <= age_seconds <= self.settings.alerts.dedupe_minutes * 60
            and previous.direction == record.direction
            and previous.metadata.get("plan_action") == record.metadata.get("plan_action")
        )

    def _suppress_alert(self, record: SignalRecord) -> AlertRecord:
        alert = AlertRecord(
            alert_id=str(uuid4()),
            signal_id=record.signal_id,
            channel=self.alert_channel.channel_name,
            status="suppressed",
            external_id=None,
            created_at=datetime.now(tz=UTC),
            error="duplicate actionable signal inside alert dedupe window",
        )
        self.repository.record_alert(alert)
        return alert


def _build_alert_channel(settings: Settings) -> object:
    if settings.alerts.dry_run:
        return DryRunAlertChannel()
    if settings.alerts.webhook_url:
        return WebhookAlertChannel(settings.alerts.webhook_url)
    return JsonlAlertChannel("logs/alerts.jsonl")


def _timeframe_minutes(timeframe: Timeframe) -> int:
    return {
        Timeframe.ONE_MINUTE: 1,
        Timeframe.FIVE_MINUTES: 5,
        Timeframe.FIFTEEN_MINUTES: 15,
        Timeframe.ONE_HOUR: 60,
        Timeframe.ONE_DAY: 1440,
    }[timeframe]
