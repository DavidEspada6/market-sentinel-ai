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
        spread_bps: float = 0.0,
        initial_equity: float = 100_000.0,
        position_fraction: float = 1.0,
    ) -> None:
        if min(fee_bps, slippage_bps, spread_bps) < 0:
            raise ValueError("trading costs cannot be negative")
        if initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if not 0 < position_fraction <= 1:
            raise ValueError("position_fraction must be in (0, 1]")
        self.feature_engine = feature_engine
        self.model = model
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.spread_bps = spread_bps
        self.initial_equity = initial_equity
        self.position_fraction = position_fraction

    def run(self, candles: Sequence[Candle]) -> BacktestReport:
        if len(candles) < 3:
            return _empty_report(self.initial_equity)

        features = self.feature_engine.transform(candles)
        gross_returns_bps: list[float] = []
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

            round_trip_cost_bps = self.fee_bps * 2 + self.slippage_bps * 2 + self.spread_bps
            gross_returns_bps.append(gross_return_bps)
            trade_returns_bps.append(gross_return_bps - round_trip_cost_bps)

        return build_backtest_report(
            trade_returns_bps,
            gross_returns_bps=gross_returns_bps,
            initial_equity=self.initial_equity,
            position_fraction=self.position_fraction,
        )


def build_backtest_report(
    returns_bps: Sequence[float],
    *,
    gross_returns_bps: Sequence[float] | None = None,
    initial_equity: float = 100_000.0,
    position_fraction: float = 1.0,
) -> BacktestReport:
    if not returns_bps:
        return _empty_report(initial_equity)
    if gross_returns_bps is None:
        gross_returns_bps = returns_bps
    if len(gross_returns_bps) != len(returns_bps):
        raise ValueError("gross and net returns must have the same length")

    wins = [value for value in returns_bps if value > 0]
    losses = [value for value in returns_bps if value < 0]
    total_profit = sum(wins)
    total_loss = abs(sum(losses))
    portfolio_returns = [value * position_fraction for value in returns_bps]
    expectancy = mean(portfolio_returns)
    std = pstdev(portfolio_returns) if len(portfolio_returns) > 1 else 0.0
    downside = [min(0.0, value) for value in portfolio_returns]
    downside_std = pstdev(downside) if len(downside) > 1 else 0.0
    equity = initial_equity
    for value in portfolio_returns:
        equity *= 1 + value / 10_000
    gross_pnl_bps = sum(gross_returns_bps)
    net_pnl_bps = sum(returns_bps)

    return BacktestReport(
        trades=len(returns_bps),
        win_rate=len(wins) / len(returns_bps),
        expectancy_bps=expectancy,
        profit_factor=(
            math.inf
            if total_loss == 0 and total_profit > 0
            else total_profit / total_loss
            if total_loss
            else 0.0
        ),
        sharpe=(expectancy / std) * math.sqrt(len(returns_bps)) if std else None,
        sortino=(expectancy / downside_std) * math.sqrt(len(returns_bps))
        if downside_std
        else None,
        max_drawdown_pct=_max_drawdown_pct(portfolio_returns),
        gross_pnl_bps=gross_pnl_bps,
        net_pnl_bps=net_pnl_bps,
        total_cost_bps=gross_pnl_bps - net_pnl_bps,
        starting_equity=initial_equity,
        ending_equity=equity,
        net_pnl=equity - initial_equity,
        total_return_pct=((equity / initial_equity) - 1) * 100,
        trade_returns_bps=tuple(returns_bps),
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


def _empty_report(initial_equity: float = 100_000.0) -> BacktestReport:
    return BacktestReport(
        trades=0,
        win_rate=0.0,
        expectancy_bps=0.0,
        profit_factor=0.0,
        sharpe=None,
        sortino=None,
        max_drawdown_pct=0.0,
        starting_equity=initial_equity,
        ending_equity=initial_equity,
    )
