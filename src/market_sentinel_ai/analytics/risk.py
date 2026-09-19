from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev

from market_sentinel_ai.domain.operations import SignalRecord
from market_sentinel_ai.domain.paper import PaperTrade
from market_sentinel_ai.domain.prediction import Direction


@dataclass(frozen=True)
class RiskMetrics:
    realized_pnl: float
    estimated_pnl: float
    unrealized_pnl: float
    total_pnl: float
    var_95: float
    cvar_95: float
    volatility_pct: float
    sharpe: float | None
    sortino: float | None
    max_drawdown_pct: float
    profit_factor: float
    win_rate: float
    expectancy: float
    exposure: float
    trades: int
    sample_size: int
    var_method: str
    var_confidence: float
    starting_equity: float

    def to_dict(self) -> dict[str, object]:
        return {
            "realized_pnl": self.realized_pnl,
            "estimated_pnl": self.estimated_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "volatility_pct": self.volatility_pct,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "max_drawdown_pct": self.max_drawdown_pct,
            "profit_factor": None if math.isinf(self.profit_factor) else self.profit_factor,
            "win_rate": self.win_rate,
            "expectancy": self.expectancy,
            "exposure": self.exposure,
            "trades": self.trades,
            "sample_size": self.sample_size,
            "var_method": self.var_method,
            "var_confidence": self.var_confidence,
            "starting_equity": self.starting_equity,
            "unrealized_note": (
                "The paper ledger records round trips only; no open positions are valued."
            ),
        }


def calculate_risk_metrics(
    trades: list[PaperTrade],
    signals: list[SignalRecord],
    *,
    starting_equity: float,
    max_position_pct: float,
    var_confidence: float = 0.95,
) -> RiskMetrics:
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")
    if not 0 < max_position_pct <= 1:
        raise ValueError("max_position_pct must be between 0 and 1")
    if not 0.5 < var_confidence < 1:
        raise ValueError("var_confidence must be between 0.5 and 1")

    realized_pnl = sum(trade.pnl for trade in trades)
    notionals = [trade.quantity * trade.entry_price for trade in trades]
    returns_pct = [
        trade.pnl / notional * 100
        for trade, notional in zip(trades, notionals, strict=True)
        if notional
    ]
    estimated_pnl = sum(
        (signal.expected_return_bps or 0.0) / 10_000 * starting_equity * max_position_pct
        for signal in signals
        if signal.direction is not Direction.NO_TRADE
    )
    var_95 = _historical_var([trade.pnl for trade in trades], var_confidence)
    cvar_95 = _historical_cvar([trade.pnl for trade in trades], var_confidence)
    average_return = mean(returns_pct) if returns_pct else 0.0
    volatility = pstdev(returns_pct) if len(returns_pct) > 1 else 0.0
    downside = [value for value in returns_pct if value < 0]
    downside_deviation = pstdev(downside) if len(downside) > 1 else 0.0
    total_profit = sum(value for value in (trade.pnl for trade in trades) if value > 0)
    total_loss = abs(sum(value for value in (trade.pnl for trade in trades) if value < 0))
    equity = starting_equity
    peak = equity
    max_drawdown = 0.0
    for trade in trades:
        equity += trade.pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
    exposure = sum(notionals)
    return RiskMetrics(
        realized_pnl=realized_pnl,
        estimated_pnl=estimated_pnl,
        unrealized_pnl=0.0,
        total_pnl=realized_pnl,
        var_95=var_95,
        cvar_95=cvar_95,
        volatility_pct=volatility,
        sharpe=(average_return / volatility) * math.sqrt(len(returns_pct))
        if volatility
        else None,
        sortino=(average_return / downside_deviation) * math.sqrt(len(returns_pct))
        if downside_deviation
        else None,
        max_drawdown_pct=max_drawdown * 100,
        profit_factor=(total_profit / total_loss)
        if total_loss
        else (math.inf if total_profit else 0.0),
        win_rate=(sum(trade.pnl > 0 for trade in trades) / len(trades)) if trades else 0.0,
        expectancy=mean(trade.pnl for trade in trades) if trades else 0.0,
        exposure=exposure,
        trades=len(trades),
        sample_size=len(trades),
        var_method="historical_pnl_quantile",
        var_confidence=var_confidence,
        starting_equity=starting_equity,
    )


def _historical_var(values: list[float], confidence: float) -> float:
    if not values:
        return 0.0
    quantile = _quantile(values, 1 - confidence)
    return max(0.0, -quantile)


def _historical_cvar(values: list[float], confidence: float) -> float:
    if not values:
        return 0.0
    threshold = -_historical_var(values, confidence)
    tail = [value for value in values if value <= threshold]
    return max(0.0, -mean(tail)) if tail else _historical_var(values, confidence)


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
