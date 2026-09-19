from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import mean, pstdev

from market_sentinel_ai.domain.market import Candle
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.ports.backtesting import BacktestReport
from market_sentinel_ai.ports.features import FeatureEngine
from market_sentinel_ai.ports.models import PredictiveModel


class SimpleBacktestEngine:
    """One-candle-ahead backtester that predicts at candle close and enters next open."""

    def __init__(
        self,
        feature_engine: FeatureEngine,
        model: PredictiveModel,
        fee_bps: float,
        slippage_bps: float,
    ) -> None:
        self.feature_engine = feature_engine
        self.model = model
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

    def run(self, candles: Sequence[Candle]) -> BacktestReport:
        if len(candles) < 3:
            return _empty_report()

        features = self.feature_engine.transform(candles)
        trade_returns_bps: list[float] = []
        for index in range(1, len(candles) - 1):
            prediction = self.model.predict(features[: index + 1])
            if prediction.direction is Direction.NO_TRADE:
                continue

            next_candle = candles[index + 1]
            gross_return_bps = (
                (next_candle.close - next_candle.open) / next_candle.open
            ) * 10_000
            if prediction.direction is Direction.SHORT:
                gross_return_bps *= -1

            round_trip_cost_bps = (self.fee_bps + self.slippage_bps) * 2
            trade_returns_bps.append(gross_return_bps - round_trip_cost_bps)

        return _report_from_returns(trade_returns_bps)


def _report_from_returns(returns_bps: Sequence[float]) -> BacktestReport:
    if not returns_bps:
        return _empty_report()

    wins = [value for value in returns_bps if value > 0]
    losses = [value for value in returns_bps if value < 0]
    total_profit = sum(wins)
    total_loss = abs(sum(losses))
    expectancy = mean(returns_bps)
    std = pstdev(returns_bps) if len(returns_bps) > 1 else 0.0
    downside = [min(0.0, value) for value in returns_bps]
    downside_std = pstdev(downside) if len(downside) > 1 else 0.0

    return BacktestReport(
        trades=len(returns_bps),
        win_rate=len(wins) / len(returns_bps),
        expectancy_bps=expectancy,
        profit_factor=math.inf if total_loss == 0 and total_profit > 0 else total_profit / total_loss
        if total_loss
        else 0.0,
        sharpe=(expectancy / std) * math.sqrt(len(returns_bps)) if std else None,
        sortino=(expectancy / downside_std) * math.sqrt(len(returns_bps))
        if downside_std
        else None,
        max_drawdown_pct=_max_drawdown_pct(returns_bps),
    )


def _max_drawdown_pct(returns_bps: Sequence[float]) -> float:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns_bps:
        equity *= 1 + value / 10_000
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown * 100


def _empty_report() -> BacktestReport:
    return BacktestReport(
        trades=0,
        win_rate=0.0,
        expectancy_bps=0.0,
        profit_factor=0.0,
        sharpe=None,
        sortino=None,
        max_drawdown_pct=0.0,
    )
