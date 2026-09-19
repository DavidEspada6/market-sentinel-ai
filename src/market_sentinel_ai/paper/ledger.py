from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from market_sentinel_ai.domain.prediction import Direction, Signal
from market_sentinel_ai.domain.risk import RiskLimits


@dataclass(frozen=True)
class PaperTrade:
    symbol: str
    direction: Direction
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    opened_at: datetime
    closed_at: datetime


class PaperTradingLedger:
    def __init__(self, starting_equity: float = 100_000.0) -> None:
        if starting_equity <= 0:
            raise ValueError("starting_equity must be positive")
        self.starting_equity = starting_equity
        self.equity = starting_equity
        self.trades: list[PaperTrade] = []

    def simulate_round_trip(
        self,
        signal: Signal,
        entry_price: float,
        exit_price: float,
        opened_at: datetime,
        closed_at: datetime,
        risk: RiskLimits,
    ) -> PaperTrade | None:
        if not signal.is_actionable:
            return None
        if signal.prediction.direction is Direction.NO_TRADE:
            return None

        notional = self.equity * risk.max_position_pct
        quantity = notional / entry_price
        gross = (exit_price - entry_price) * quantity
        if signal.prediction.direction is Direction.SHORT:
            gross *= -1
        costs = notional * (
            (risk.fee_bps * 2 + risk.slippage_bps * 2 + risk.spread_bps) / 10_000
        )
        pnl = gross - costs
        trade = PaperTrade(
            symbol=signal.prediction.symbol,
            direction=signal.prediction.direction,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            opened_at=opened_at,
            closed_at=closed_at,
        )
        self.trades.append(trade)
        self.equity += pnl
        return trade

    @property
    def total_pnl(self) -> float:
        return self.equity - self.starting_equity
