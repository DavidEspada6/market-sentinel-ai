from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from market_sentinel_ai.domain.prediction import Direction


@dataclass(frozen=True)
class PaperPosition:
    position_id: str
    account_id: str
    symbol: str
    direction: Direction
    quantity: float
    entry_price: float
    mark_price: float
    leverage: float
    margin: float
    entry_cost: float
    opened_at: datetime
    updated_at: datetime
    stop_loss: float | None = None
    take_profit: float | None = None

    @property
    def notional(self) -> float:
        return self.quantity * self.entry_price

    @property
    def mark_notional(self) -> float:
        return self.quantity * self.mark_price

    @property
    def gross_unrealized_pnl(self) -> float:
        difference = self.mark_price - self.entry_price
        if self.direction is Direction.SHORT:
            difference *= -1
        return difference * self.quantity


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
    margin: float = 0.0
    leverage: float = 1.0
    entry_cost: float = 0.0
    exit_cost: float = 0.0
    notional: float = 0.0
    close_reason: str = "manual"


@dataclass(frozen=True)
class PaperTradeRecord:
    trade_id: str
    account_id: str
    trade: PaperTrade


@dataclass(frozen=True)
class PaperAccountSnapshot:
    account_id: str
    starting_equity: float
    equity: float
    updated_at: datetime
    real_execution_enabled: bool = False
