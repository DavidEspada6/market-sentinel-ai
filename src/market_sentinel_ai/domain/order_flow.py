from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    size: float

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("price must be positive")
        if self.size < 0:
            raise ValueError("size cannot be negative")


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    captured_at: datetime
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]

    @property
    def best_bid(self) -> float:
        return max(level.price for level in self.bids)

    @property
    def best_ask(self) -> float:
        return min(level.price for level in self.asks)

    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2

    @property
    def spread_bps(self) -> float:
        return ((self.best_ask - self.best_bid) / self.mid_price) * 10_000

    @property
    def imbalance(self) -> float:
        bid_size = sum(level.size for level in self.bids)
        ask_size = sum(level.size for level in self.asks)
        total = bid_size + ask_size
        return (bid_size - ask_size) / total if total else 0.0

