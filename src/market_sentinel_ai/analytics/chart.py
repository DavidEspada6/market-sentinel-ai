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
    TEN_MINUTES = "10m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
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
    ChartWindow.TEN_MINUTES: ChartWindowSpec(
        ChartWindow.TEN_MINUTES, "10 minutos", timedelta(minutes=10), Timeframe.FIVE_MINUTES
    ),
    ChartWindow.THIRTY_MINUTES: ChartWindowSpec(
        ChartWindow.THIRTY_MINUTES, "30 minutos", timedelta(minutes=30), Timeframe.FIVE_MINUTES
    ),
    ChartWindow.ONE_HOUR: ChartWindowSpec(
        ChartWindow.ONE_HOUR, "1 hora", timedelta(hours=1), Timeframe.FIVE_MINUTES
    ),
    ChartWindow.TWO_HOURS: ChartWindowSpec(
        ChartWindow.TWO_HOURS, "2 horas", timedelta(hours=2), Timeframe.FIVE_MINUTES
    ),
    ChartWindow.SIX_HOURS: ChartWindowSpec(
        ChartWindow.SIX_HOURS, "6 horas", timedelta(hours=6), Timeframe.FIVE_MINUTES
    ),
    ChartWindow.TWELVE_HOURS: ChartWindowSpec(
        ChartWindow.TWELVE_HOURS, "12 horas", timedelta(hours=12), Timeframe.FIVE_MINUTES
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
    data_notice: str | None = None,
    market_context: dict[str, object] | None = None,
) -> dict[str, object]:
    latest = candles[-1]
    first_close = candles[0].close
    change_pct = ((latest.close - first_close) / first_close) * 100 if first_close else 0.0
    forecast = _build_forecast(candles, signal, plan, feature)
    explanation = _build_explanation(latest, signal, plan, feature, market_context)
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
        "data_as_of": latest.opened_at.isoformat(),
        "data_notice": data_notice,
        "market_context": market_context or {},
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
            "metadata": signal.prediction.metadata,
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
        "explanation": explanation,
        "forecast": forecast,
        "disclaimer": (
            (
                "ESPERAR: no hay una dirección suficientemente clara para comprar o vender. "
                "La zona amarilla es un rango de incertidumbre basado en volatilidad y momentum."
                if signal.prediction.direction.value == "NO_TRADE"
                else (
                    f"Señal {signal.prediction.direction.value}: el modelo estima un sesgo "
                    "direccional, pero la banda amarilla muestra la incertidumbre del escenario "
                    "futuro aproximado."
                )
            )
            + " No es una garantía ni una orden de inversión."
        ),
    }


def _build_explanation(
    candle: Candle,
    signal: Signal,
    plan: TradePlan,
    feature: FeatureRow,
    market_context: dict[str, object] | None = None,
) -> dict[str, object]:
    values = feature.values
    direction = signal.prediction.direction
    momentum = float(values.get("rolling_return_mean_bps", 0.0))
    ema_cross = float(values.get("ema_cross_bps", 0.0))
    ema_slope = float(values.get("ema_cross_slope_bps", 0.0))
    rsi = float(values.get("rsi", 50.0))
    bollinger = float(values.get("bollinger_position", 0.5))
    volume_zscore = float(values.get("volume_zscore", 0.0))
    atr_bps = max(float(values.get("atr_bps", 0.0)), 1.0)
    expected = signal.prediction.expected_return_bps

    drivers: list[str] = []
    warnings: list[str] = []
    if direction is Direction.LONG:
        bias_word = "alcista"
        _append_directional_driver(
            drivers,
            warnings,
            momentum,
            "El momentum medio es positivo ({value:+.1f} bps), a favor de la subida.",
            "El momentum medio es negativo ({value:+.1f} bps), en contra de la subida.",
            "El momentum es débil ({value:+.1f} bps) y aporta poca confirmación.",
            supports_positive=True,
        )
        _append_directional_driver(
            drivers,
            warnings,
            ema_cross,
            "La EMA rápida está por encima de la lenta ({value:+.1f} bps).",
            "La EMA rápida está por debajo de la lenta ({value:+.1f} bps).",
            "Las medias están prácticamente cruzadas ({value:+.1f} bps).",
            supports_positive=True,
        )
        if rsi >= 55:
            drivers.append(f"El RSI está en {rsi:.1f}, compatible con presión compradora.")
        else:
            warnings.append(
                f"El RSI está en {rsi:.1f}, por debajo de 55 y sin confirmación alcista fuerte."
            )
        if bollinger >= 0.55:
            drivers.append(
                f"El precio ocupa {bollinger:.0%} del canal de Bollinger, en la mitad superior."
            )
        else:
            warnings.append(
                f"El precio ocupa {bollinger:.0%} del canal de Bollinger, todavía en la "
                "mitad inferior."
            )
        if rsi > 70:
            warnings.append("El RSI está sobrecomprado; la subida puede estar extendida.")
    elif direction is Direction.SHORT:
        bias_word = "bajista"
        _append_directional_driver(
            drivers,
            warnings,
            momentum,
            "El momentum medio es negativo ({value:+.1f} bps), a favor de la bajada.",
            "El momentum medio es positivo ({value:+.1f} bps), en contra de la bajada.",
            "El momentum es débil ({value:+.1f} bps) y aporta poca confirmación.",
            supports_positive=False,
        )
        _append_directional_driver(
            drivers,
            warnings,
            ema_cross,
            "La EMA rápida está por debajo de la lenta ({value:+.1f} bps).",
            "La EMA rápida está por encima de la lenta ({value:+.1f} bps).",
            "Las medias están prácticamente cruzadas ({value:+.1f} bps).",
            supports_positive=False,
        )
        if rsi <= 45:
            drivers.append(f"El RSI está en {rsi:.1f}, compatible con presión vendedora.")
        else:
            warnings.append(
                f"El RSI está en {rsi:.1f}, por encima de 45 y sin confirmación bajista fuerte."
            )
        if bollinger <= 0.45:
            drivers.append(
                f"El precio ocupa {bollinger:.0%} del canal de Bollinger, en la mitad inferior."
            )
        else:
            warnings.append(
                f"El precio ocupa {bollinger:.0%} del canal de Bollinger, todavía en la "
                "mitad superior."
            )
        if rsi < 30:
            warnings.append("El RSI está sobrevendido; la bajada puede estar extendida.")
    else:
        bias_word = "indefinido"
        drivers.append("El modelo no reúne suficiente ventaja direccional después de costes.")
        if abs(momentum) >= 0.5:
            drivers.append(
                f"Hay momentum ({momentum:+.1f} bps), pero no supera todos los filtros de entrada."
            )
        if abs(ema_cross) >= 1.0:
            drivers.append(
                f"Las medias muestran una separación de {ema_cross:+.1f} bps, con señal "
                "no concluyente."
            )
        warnings.append("La lectura correcta es esperar; no se fuerza una compra ni una venta.")

    if volume_zscore >= 0.5:
        drivers.append(
            f"El volumen está por encima de su media (z-score {volume_zscore:+.1f}), "
            "dando más participación al movimiento."
        )
    elif volume_zscore <= -0.5:
        warnings.append(
            f"El volumen está por debajo de su media (z-score {volume_zscore:+.1f}); "
            "la señal tiene menor confirmación."
        )
    if abs(ema_slope) >= 0.5:
        drivers.append(f"La pendiente reciente del cruce de medias es {ema_slope:+.1f} bps.")
    context = market_context or {}
    news_count = int(context.get("news_count", 0))
    news_score = float(context.get("sentiment_score", 0.0))
    news_label = str(context.get("sentiment_label", "neutral"))
    if news_count:
        drivers.append(
            f"El contexto de {news_count} titulares recientes es {news_label} "
            f"(score {news_score:+.2f}); solo ajusta la confianza, no sustituye al precio."
        )
    elif str(context.get("news_status", "")).startswith("unavailable"):
        warnings.append(
            "No se pudo consultar el contexto de noticias; la lectura usa solo mercado."
        )
    if not drivers:
        drivers.append(
            "No hay indicadores suficientes para explicar una ventaja direccional clara."
        )

    probability = signal.prediction.probability * 100
    expected_text = "sin estimación de retorno"
    if expected is not None:
        expected_text = f"retorno esperado {expected:+.1f} bps"
    if direction is Direction.NO_TRADE:
        summary = (
            f"Lectura {bias_word.upper()}: el modelo tiene {probability:.1f}% de probabilidad y "
            f"{expected_text}; la combinación no alcanza el umbral operativo."
        )
    else:
        summary = (
            f"Lectura {bias_word.upper()}: el modelo combina momentum, medias, RSI y volatilidad "
            f"con {probability:.1f}% de probabilidad y {expected_text}."
        )

    if plan.entry_price is None:
        level_explanations = [
            "No hay entrada ni objetivo propuestos porque la señal está en ESPERAR.",
            "La volatilidad actual (ATR) es de aproximadamente "
            f"{atr_bps:.1f} bps, pero no se convierte en una orden sin dirección suficiente.",
        ]
    else:
        risk_bps = plan.risk_bps or 0.0
        reward_bps = plan.reward_bps or 0.0
        ratio = plan.reward_risk_ratio or 0.0
        direction_word = "por encima" if direction is Direction.LONG else "por debajo"
        level_explanations = [
            f"Entrada {plan.entry_price:.6f}: usa el último cierre confirmado "
            f"({candle.opened_at.isoformat()}).",
            f"Objetivo {plan.take_profit_price:.6f}: se coloca {direction_word} de la entrada "
            f"con {reward_bps:.1f} bps de recorrido y ratio riesgo/beneficio {ratio:.2f}.",
            f"Stop {plan.stop_loss_price:.6f}: usa {risk_bps:.1f} bps de riesgo, basado "
            f"principalmente en 1.5x ATR ({atr_bps:.1f} bps) y el coste estimado.",
            f"El plan deja de ser válido aproximadamente en {plan.valid_until_iso}; los precios "
            "son niveles de referencia, no ejecuciones garantizadas.",
        ]
    return {
        "summary": summary,
        "drivers": drivers[:6],
        "warnings": warnings[:4],
        "levels": level_explanations,
    }


def _append_directional_driver(
    drivers: list[str],
    warnings: list[str],
    value: float,
    positive_text: str,
    negative_text: str,
    neutral_text: str,
    *,
    supports_positive: bool,
) -> None:
    supports = value >= 0.5 if supports_positive else value <= -0.5
    opposes = value <= -0.5 if supports_positive else value >= 0.5
    if supports:
        drivers.append(positive_text.format(value=value))
    elif opposes:
        warnings.append(negative_text.format(value=value))
    else:
        warnings.append(neutral_text.format(value=value))


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
        expected_move = direction_sign * abs(expected_bps) * progress / 10_000
        central_price = close * (1 + expected_move)
        spread = close * atr_bps / 10_000 * sqrt(progress)
        timestamp = latest.opened_at + timedelta(minutes=step_minutes * step)
        iso_timestamp = timestamp.isoformat()
        center.append({"time": iso_timestamp, "value": central_price})
        upper.append({"time": iso_timestamp, "value": central_price + spread})
        lower.append({"time": iso_timestamp, "value": max(0.000001, central_price - spread)})

    return {
        "method": f"ATR envelope + {signal.prediction.model_name} scenario",
        "upper": upper,
        "center": center,
        "lower": lower,
        "direction": direction.value,
        "horizon_minutes": signal.prediction.horizon_minutes,
        "atr_bps": atr_bps,
        "entry": plan.entry_price,
        "stop": plan.stop_loss_price,
        "target": plan.take_profit_price,
    }
