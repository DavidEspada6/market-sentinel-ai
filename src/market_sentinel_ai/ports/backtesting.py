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


class BacktestEngine(Protocol):
    def run(self, candles: Sequence[Candle]) -> BacktestReport:
        """Run a leakage-aware backtest over time-ordered candles."""

