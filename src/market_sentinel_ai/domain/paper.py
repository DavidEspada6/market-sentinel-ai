from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from market_sentinel_ai.domain.prediction import Direction


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
