from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from market_sentinel_ai.domain.market import Candle


@dataclass(frozen=True)
class BacktestReport:
    trades: int
    win_rate: float
    expectancy_bps: float
    profit_factor: float
    sharpe: float | None
    sortino: float | None
    max_drawdown_pct: float
    gross_pnl_bps: float = 0.0
    net_pnl_bps: float = 0.0
    total_cost_bps: float = 0.0
    starting_equity: float = 0.0
    ending_equity: float = 0.0
    net_pnl: float = 0.0
    total_return_pct: float = 0.0
    trade_returns_bps: tuple[float, ...] = ()


class BacktestEngine(Protocol):
    def run(self, candles: Sequence[Candle]) -> BacktestReport:
        """Run a leakage-aware backtest over time-ordered candles."""
