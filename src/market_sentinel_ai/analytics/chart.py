from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from math import sqrt

from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.prediction import Direction, Signal
from market_sentinel_ai.ports.features import FeatureRow
from market_sentinel_ai.signals.trade_plan import TradePlan


class ChartWindow(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"
    SIX_MONTHS = "6mo"
    ONE_YEAR = "1y"
    THREE_YEARS = "3y"
    TOTAL = "total"


@dataclass(frozen=True)
class ChartWindowSpec:
    window: ChartWindow
    label: str
    lookback: timedelta | None
    timeframe: Timeframe


_WINDOW_SPECS: dict[ChartWindow, ChartWindowSpec] = {
    ChartWindow.ONE_MINUTE: ChartWindowSpec(
        ChartWindow.ONE_MINUTE, "1 minuto", timedelta(minutes=1), Timeframe.ONE_MINUTE
    ),
    ChartWindow.FIVE_MINUTES: ChartWindowSpec(
        ChartWindow.FIVE_MINUTES, "5 minutos", timedelta(minutes=5), Timeframe.FIVE_MINUTES
    ),
    ChartWindow.THIRTY_MINUTES: ChartWindowSpec(
        ChartWindow.THIRTY_MINUTES, "30 minutos", timedelta(minutes=30), Timeframe.FIVE_MINUTES
    ),
    ChartWindow.ONE_HOUR: ChartWindowSpec(
        ChartWindow.ONE_HOUR, "1 hora", timedelta(hours=1), Timeframe.FIVE_MINUTES
    ),
    ChartWindow.SIX_HOURS: ChartWindowSpec(
        ChartWindow.SIX_HOURS, "6 horas", timedelta(hours=6), Timeframe.FIFTEEN_MINUTES
    ),
    ChartWindow.TWELVE_HOURS: ChartWindowSpec(
        ChartWindow.TWELVE_HOURS, "12 horas", timedelta(hours=12), Timeframe.FIFTEEN_MINUTES
    ),
    ChartWindow.ONE_DAY: ChartWindowSpec(
        ChartWindow.ONE_DAY, "1 día", timedelta(days=1), Timeframe.ONE_HOUR
    ),
    ChartWindow.ONE_WEEK: ChartWindowSpec(
        ChartWindow.ONE_WEEK, "1 semana", timedelta(days=7), Timeframe.ONE_HOUR
    ),
    ChartWindow.ONE_MONTH: ChartWindowSpec(
        ChartWindow.ONE_MONTH, "1 mes", timedelta(days=30), Timeframe.ONE_DAY
    ),
    ChartWindow.THREE_MONTHS: ChartWindowSpec(
        ChartWindow.THREE_MONTHS, "3 meses", timedelta(days=90), Timeframe.ONE_DAY
    ),
    ChartWindow.SIX_MONTHS: ChartWindowSpec(
        ChartWindow.SIX_MONTHS, "6 meses", timedelta(days=180), Timeframe.ONE_DAY
    ),
    ChartWindow.ONE_YEAR: ChartWindowSpec(
        ChartWindow.ONE_YEAR, "1 año", timedelta(days=365), Timeframe.ONE_DAY
    ),
    ChartWindow.THREE_YEARS: ChartWindowSpec(
        ChartWindow.THREE_YEARS, "3 años", timedelta(days=1095), Timeframe.ONE_DAY
    ),
    ChartWindow.TOTAL: ChartWindowSpec(
        ChartWindow.TOTAL, "Total disponible", None, Timeframe.ONE_DAY
    ),
}

_TIMEFRAME_MINUTES: dict[Timeframe, int] = {
    Timeframe.ONE_MINUTE: 1,
    Timeframe.FIVE_MINUTES: 5,
    Timeframe.FIFTEEN_MINUTES: 15,
    Timeframe.ONE_HOUR: 60,
    Timeframe.ONE_DAY: 1440,
}


def chart_window_spec(value: str) -> ChartWindowSpec:
    try:
        return _WINDOW_SPECS[ChartWindow(value)]
    except (KeyError, ValueError) as exc:
        supported = ", ".join(item.value for item in ChartWindow)
        raise ValueError(f"unsupported chart window; use one of: {supported}") from exc


def chart_window_specs() -> tuple[ChartWindowSpec, ...]:
    return tuple(_WINDOW_SPECS[item] for item in ChartWindow)


def timeframe_minutes(timeframe: Timeframe) -> int:
    return _TIMEFRAME_MINUTES[timeframe]


def build_market_chart_payload(
    candles: list[Candle],
    signal: Signal,
    plan: TradePlan,
    feature: FeatureRow,
    *,
    instrument: dict[str, object],
    spec: ChartWindowSpec,
    provider: str,
    source: str,
) -> dict[str, object]:
    latest = candles[-1]
    first_close = candles[0].close
    change_pct = ((latest.close - first_close) / first_close) * 100 if first_close else 0.0
    forecast = _build_forecast(candles, signal, plan, feature)
    return {
        "symbol": instrument["symbol"],
        "market_symbol": latest.symbol,
        "name": instrument["name"],
        "asset_class": instrument["asset_class"],
        "currency": instrument["currency"],
        "window": spec.window.value,
        "window_label": spec.label,
        "timeframe": spec.timeframe.value,
        "provider": provider,
        "source": source,
        "candle_count": len(candles),
        "change_pct": change_pct,
        "candles": [_candle_to_dict(candle) for candle in candles],
        "latest": {
            "time": latest.opened_at.isoformat(),
            "close": latest.close,
            "high": latest.high,
            "low": latest.low,
            "volume": latest.volume,
        },
        "signal": {
            "action": plan.action,
            "direction": signal.prediction.direction.value,
            "confidence": signal.confidence,
            "expected_return_bps": signal.prediction.expected_return_bps,
            "horizon_minutes": signal.prediction.horizon_minutes,
            "model": signal.prediction.model_name,
            "rationale": signal.rationale,
        },
        "levels": {
            "entry": plan.entry_price,
            "stop": plan.stop_loss_price,
            "target": plan.take_profit_price,
            "risk_bps": plan.risk_bps,
            "reward_bps": plan.reward_bps,
            "reward_risk_ratio": plan.reward_risk_ratio,
            "valid_until": plan.valid_until_iso,
        },
        "forecast": forecast,
        "disclaimer": (
            "Las líneas futuras son un escenario aproximado basado en volatilidad y momentum; "
            "no son una garantía ni una orden de inversión."
        ),
    }


def _candle_to_dict(candle: Candle) -> dict[str, object]:
    return {
        "time": candle.opened_at.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


def _build_forecast(
    candles: list[Candle],
    signal: Signal,
    plan: TradePlan,
    feature: FeatureRow,
    *,
    steps: int = 6,
) -> dict[str, object]:
    latest = candles[-1]
    close = latest.close
    atr_bps = max(float(feature.values.get("atr_bps", 0.0)), 1.0)
    expected_bps = float(signal.prediction.expected_return_bps or 0.0)
    direction = signal.prediction.direction
    direction_sign = 1 if direction is Direction.LONG else -1 if direction is Direction.SHORT else 0
    step_minutes = timeframe_minutes(latest.timeframe)
    horizon_steps = max(1, round(signal.prediction.horizon_minutes / step_minutes))
    upper: list[dict[str, object]] = []
    lower: list[dict[str, object]] = []
    center: list[dict[str, object]] = []
    for step in range(1, steps + 1):
        progress = min(1.0, step / horizon_steps)
        expected_move = direction_sign * expected_bps * progress / 10_000
        central_price = close * (1 + expected_move)
        spread = close * atr_bps / 10_000 * sqrt(progress)
        timestamp = latest.opened_at + timedelta(minutes=step_minutes * step)
        iso_timestamp = timestamp.isoformat()
        center.append({"time": iso_timestamp, "value": central_price})
        upper.append({"time": iso_timestamp, "value": central_price + spread})
        lower.append({"time": iso_timestamp, "value": max(0.000001, central_price - spread)})

    return {
        "method": "ATR envelope + momentum-baseline scenario",
        "upper": upper,
        "center": center,
        "lower": lower,
        "horizon_minutes": signal.prediction.horizon_minutes,
        "atr_bps": atr_bps,
        "entry": plan.entry_price,
        "stop": plan.stop_loss_price,
        "target": plan.take_profit_price,
    }
