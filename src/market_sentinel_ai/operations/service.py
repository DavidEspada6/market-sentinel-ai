from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from market_sentinel_ai.adapters.market_data import build_market_data_provider
from market_sentinel_ai.alerts import DryRunAlertChannel, JsonlAlertChannel, WebhookAlertChannel
from market_sentinel_ai.config import Settings
from market_sentinel_ai.domain.market import Timeframe
from market_sentinel_ai.domain.operations import AlertRecord, SignalRecord
from market_sentinel_ai.features import OHLCVFeatureEngine
from market_sentinel_ai.ingestion import MarketDataIngestionService
from market_sentinel_ai.models import MomentumBaselineModel
from market_sentinel_ai.signals import SignalEngine
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

        features = OHLCVFeatureEngine().transform(candles)
        horizon_minutes = _timeframe_minutes(timeframe)
        prediction = MomentumBaselineModel(horizon_minutes=horizon_minutes).predict(features)
        round_trip_cost_bps = (
            self.settings.risk.default_fee_bps * 2
            + self.settings.risk.default_slippage_bps * 2
            + self.settings.risk.default_spread_bps
        )
        signal = SignalEngine(
            min_probability=0.55,
            min_expected_return_bps=round_trip_cost_bps,
        ).from_prediction(prediction)
        record = SignalRecord.from_signal(str(uuid4()), timeframe.value, signal)
        self.repository.record_signal(record)

        alerts: list[AlertRecord] = []
        if signal.is_actionable:
            alerts.append(self._send_alert(record, signal))

        return ScanResult(
            signal=record,
            alerts=tuple(alerts),
            candle_count=len(candles),
            ingestion_run_id=ingestion.run.run_id,
        )

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
